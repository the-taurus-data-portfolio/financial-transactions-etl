"""
ETL Pipeline orchestrator for bank transaction processing.

Manages the complete flow from CSV input through intermediate format to target system format.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import io

import pandas as pd

from core.config_manager import ConfigManager
from core.schema_loader import YamlSchemaLoader
from converters.target_converter_manager import TargetConverterManager
from converters.generic_source_converter import GenericSourceConverter
from converters.citadele_source_converter import CitadeleSourceConverter
from utils.logging_config import setup_logging
from converters.bank_detector import BankDetector
from core.source_providers import SourceProviderFactory
from core.archivers import ArchiverFactory
from utils.csv_utils import copy_df_to_clipboard


class ETLPipeline:
    """
    Main ETL pipeline orchestrator for bank transaction processing.

    Coordinates:
    - Data ingestion via SourceProvider
    - Bank detection from CSV headers
    - Conversion from bank format to intermediate format
    - Conversion from intermediate format to target system format
    - Output generation (file and console)
    - Optional: Copying to clipboard and archiving via SourceArchiver
    """

    _CONVERTER_MAP = {
        'citadele': CitadeleSourceConverter,
    }

    def __init__(self, config_path: str):
        """
        Initialize the ETL Pipeline orchestrator.

        Args:
            config_path: Path to the main configuration file.
        """
        self.config = None
        self.schema_loader = None
        self.target_converter_manager = None
        self.logger = None
        self.bank_detector = None
        self.source_provider = None
        self.archiver = None

        self._initialize(config_path)

    def _initialize(self, config_path: str) -> None:
        """Initialize all pipeline components."""
        try:
            self.config = ConfigManager(config_path)
            logging_config = self.config.get_logging_config()
            setup_logging(logging_config)
            self.logger = logging.getLogger(__name__)
            self.config.ensure_directories()

            paths_config = self.config.get_paths_config()
            self.schema_loader = YamlSchemaLoader(
                schemas_dir=paths_config['schemas_dir'],
                mappings_dir=paths_config['mappings_dir']
            )

            # Initialize target converter manager
            self.logger.info("Initializing target converters...")
            self.target_converter_manager = TargetConverterManager(self.config, self.schema_loader, self.logger)
            self.target_converter_manager.initialize_converters()

            # Initialize bank detector for header-based bank detection
            self.logger.info("Loading bank header signatures...")
            self.bank_detector = BankDetector(self.config, self.logger)

            # Initialize source provider
            self.logger.info("Initializing source provider...")
            self.source_provider = SourceProviderFactory.create(self.config, self.logger)

            # Initialize archiver
            self.archiver = ArchiverFactory.create(self.config, self.logger)

            self.logger.info("ETL Pipeline initialized successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize ETL pipeline: {e}")
            else:
                print(f"FATAL: Failed to initialize ETL pipeline: {e}")
            raise

    def process_single_file(
        self, file_metadata: Dict[str, Any], file_content: io.BytesIO, override_bank_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a single CSV file's content through the complete pipeline.

        Args:
            file_metadata: Dictionary with file metadata (name, identifier)
            file_content: BytesIO buffer with CSV content
            override_bank_type: Optional bank type to override auto-detection

        Returns:
            Processing results dictionary
        """
        file_name = file_metadata['name']
        file_id = file_metadata['identifier']
        self.logger.info(f"Processing file: {file_name} (ID: {file_id})")

        # Get default target converter and its name
        target_converter = self.target_converter_manager.get_default_converter()
        target_name = self.target_converter_manager.get_default_target_name()

        results = {
            'file_name': file_name,
            'file_identifier': file_id,
            'success': False,
            'error': None,
            'bank_type': None,
            'intermediate_rows': 0,
            'target_rows': 0,
            'intermediate_data': None,
            'target_data': None,
            'target_name': target_name
        }

        source_converters_config = self.config.get('source_converters', {})
        if not source_converters_config:
            error_msg = "No 'source_converters' defined in the configuration"
            self.logger.error(error_msg)
            results['error'] = error_msg
            return results

        # Determine bank type
        detected_bank_type = override_bank_type
        matched_sample_file = None
        if not detected_bank_type:
            detected_bank_type, matched_sample_file = self.bank_detector.detect_bank_from_header(file_content)

        if not detected_bank_type:
            error_msg = f"Could not determine bank type for file '{file_name}'"
            self.logger.warning(error_msg)
            results['error'] = error_msg
            return results

        results['bank_type'] = detected_bank_type

        # Validate bank configuration exists
        source_config_params = source_converters_config.get(detected_bank_type)
        if not source_config_params:
            error_msg = f"Configuration for bank type '{detected_bank_type}' not found"
            self.logger.error(error_msg)
            results['error'] = error_msg
            return results

        # Extract schema and mapping configuration
        source_schema_name = source_config_params.get('source_schema')
        mapping_name = source_config_params.get('mapping')

        if not source_schema_name or not mapping_name:
            error_msg = (
                f"Incomplete configuration for bank '{detected_bank_type}': "
                f"missing 'source_schema' or 'mapping'"
            )
            self.logger.error(error_msg)
            results['error'] = error_msg
            return results

        # Get primary sample file
        primary_sample_file = self.bank_detector.get_primary_sample_file(detected_bank_type)

        # Initialize converter — bank-specific subclass when available
        try:
            converter_cls = self._CONVERTER_MAP.get(detected_bank_type, GenericSourceConverter)
            source_converter = converter_cls(
                schema_loader=self.schema_loader,
                bank_type=detected_bank_type,
                source_schema_name=source_schema_name,
                mapping_rules_name=mapping_name,
                matched_sample_file=matched_sample_file,
                primary_sample_file=primary_sample_file
            )
        except Exception as e:
            error_msg = f"Failed to initialize converter for '{detected_bank_type}': {e}"
            self.logger.error(error_msg)
            results['error'] = error_msg
            return results

        try:
            # Step 1: Convert source content to intermediate
            self.logger.info("Step 1: Converting source content to intermediate format")
            intermediate_df = source_converter.process_content(file_content)

            if len(intermediate_df) == 0:
                self.logger.warning("No data produced in intermediate format")
                return results

            results['intermediate_rows'] = len(intermediate_df)
            results['intermediate_data'] = intermediate_df

            # Step 2: Convert intermediate to target format
            self.logger.info(f"Step 2: Converting intermediate to {target_name} format")
            target_df = target_converter.transform_to_target(intermediate_df)

            results['target_rows'] = len(target_df)
            results['target_data'] = target_df
            results['success'] = True

            self.logger.info(f"Successfully processed {file_name}: "
                             f"{results['intermediate_rows']} -> {results['target_rows']} transactions")

        except Exception as e:
            error_msg = f"Failed to process {file_name}: {e}"
            self.logger.error(error_msg)
            results['error'] = str(e)

            if self.config.is_strict_mode():
                raise

        return results

    def save_outputs(self, all_results: List[Dict[str, Any]]) -> None:
        """
        Save processing outputs according to configuration.

        Args:
            all_results: List of processing results
        """
        # Combine all successful results
        intermediate_dfs = []
        target_dfs = []

        for result in all_results:
            if result['success'] and result['intermediate_data'] is not None:
                intermediate_dfs.append(result['intermediate_data'])
            if result['success'] and result['target_data'] is not None:
                target_dfs.append(result['target_data'])

        if not intermediate_dfs and not target_dfs:
            self.logger.warning("No data to save")
            return

        # Get source converter to use for intermediate output
        source_converter = GenericSourceConverter(
            schema_loader=self.schema_loader,
            bank_type='generic',
            source_schema_name='intermediate.yaml',  # Not used but required
            mapping_rules_name='intermediate_to_tiller.yaml'  # Not used but required
        ) if intermediate_dfs else None

        # Combine DataFrames
        if intermediate_dfs and source_converter:
            combined_intermediate = pd.concat(intermediate_dfs, ignore_index=True)
            source_converter.save_output(combined_intermediate, self.config)

        if target_dfs:
            combined_target = pd.concat(target_dfs, ignore_index=True)
            target_converter = self.target_converter_manager.get_default_converter()
            target_name = self.target_converter_manager.get_default_target_name()
            target_converter.save_output(combined_target, self.config, target_name)

            # Copy to clipboard if enabled in config
            if self.config.get('processing', {}).get('copy_to_clipboard', False):
                copy_df_to_clipboard(combined_target, self.logger)

    def run(self, input_dir: Optional[str] = None, override_bank_type: Optional[str] = None) -> bool:
        """
        Run the complete ETL pipeline.

        Args:
            input_dir: Optional override for local input directory
            override_bank_type: Optional bank type to override auto-detection

        Returns:
            True if processing was successful, False otherwise
        """
        self.logger.info("Starting ETL pipeline")

        # Handle local input_dir override if provider is local
        if input_dir and hasattr(self.source_provider, 'input_dir'):
            self.logger.info(f"Overriding local input directory: {input_dir}")
            self.source_provider.input_dir = input_dir

        try:
            # Find input files via provider
            files_metadata = self.source_provider.list_files()

            if not files_metadata:
                self.logger.error("No files found to process")
                return False

            self.logger.info(f"Found {len(files_metadata)} files to process")

            # Process all files
            all_results = []
            successful_identifiers = []

            for metadata in files_metadata:
                try:
                    content = self.source_provider.get_file_content(metadata['identifier'])
                    result = self.process_single_file(metadata, content, override_bank_type)
                    all_results.append(result)

                    if result['success']:
                        successful_identifiers.append(metadata['identifier'])
                except Exception as e:
                    self.logger.error(f"Failed to fetch content for {metadata['name']}: {e}")
                    all_results.append({
                        'file_name': metadata['name'],
                        'success': False,
                        'error': str(e)
                    })

            # Save outputs
            if len(successful_identifiers) > 0:
                self.logger.info(f"Saving outputs for {len(successful_identifiers)} file(s)...")
                self.save_outputs(all_results)

            # Summary
            total_files = len(files_metadata)
            count_successful = len(successful_identifiers)
            failed_files = total_files - count_successful

            self.logger.info(f"ETL Pipeline completed: {count_successful}/{total_files} files processed successfully")

            # Archive source files if enabled and ALL files were successful
            if self.archiver and count_successful == total_files:
                self.logger.info("Archiving source files (Batch success)")
                self.archiver.archive(successful_identifiers)
            elif self.archiver and failed_files > 0:
                self.logger.warning(f"Skipping archiving because {failed_files} file(s) failed")

            if failed_files > 0:
                self.logger.warning(f"{failed_files} files failed to process")
                for result in all_results:
                    if not result['success']:
                        self.logger.error(f"Failed: {result.get('file_name')} - {result['error']}")

            return count_successful > 0

        except Exception as e:
            self.logger.error(f"ETL pipeline failed: {e}")
            return False
