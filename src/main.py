#!/usr/bin/env python3
"""
Main entry point for the Bank to Tiller ETL pipeline.
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.schema_loader import YamlSchemaLoader
from converters.generic_source_converter import GenericSourceConverter
from converters.tiller_converter import TillerConverter
from utils.logging_config import setup_logging


class ETLPipeline:
    """
    Main ETL pipeline orchestrator.
    """

    def __init__(self, config_path: str):
        """
        Initialize the ETL Pipeline orchestrator.

        Args:
            config_path: Path to the main configuration file.
        """
        self.config = None
        self.schema_loader = None
        self.source_converter = None
        self.target_converter = None
        self.logger = None # Initialize logger here, will be set up properly in _initialize

        self._initialize(config_path)



    def _initialize(self, config_path: str) -> None:
        """Initialize all components."""
        try:
            # Load configuration
            self.config = ConfigManager(config_path)

            # Setup logging
            logging_config = self.config.get_logging_config()
            setup_logging(logging_config)
            self.logger = logging.getLogger(__name__)

            # Ensure required directories exist
            self.config.ensure_directories()

            # Initialize schema loader
            paths_config = self.config.get_paths_config()
            self.schema_loader = YamlSchemaLoader(
                schemas_dir=paths_config['schemas_dir'],
                mappings_dir=paths_config['mappings_dir']
            )

            # Initialize converters
            # self.source_converter = SwedbankConverter(self.schema_loader)
            # IMPORTANT: TillerConverter also needs schema_loader
            self.target_converter = TillerConverter(self.schema_loader, self.config.get_tiller_history_source())

            self.logger.info("ETL Pipeline initialized successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize ETL pipeline: {e}")
            else:
                print(f"FATAL: Failed to initialize ETL pipeline: {e}")
            raise

    def find_csv_files(self, input_dir: str) -> List[Path]:
        """
        Find all CSV files in the input directory.

        Args:
            input_dir: Directory to search for CSV files

        Returns:
            List of CSV file paths
        """
        input_path = Path(input_dir)

        if not input_path.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")

        if not input_path.is_dir():
            raise ValueError(f"Input path is not a directory: {input_dir}")

        # Get supported extensions
        supported_extensions = self.config.get_supported_extensions()

        csv_files = []
        for ext in supported_extensions:
            csv_files.extend(input_path.glob(f"*{ext}"))

        if not csv_files:
            self.logger.warning(f"No CSV files found in {input_dir}")
        else:
            self.logger.info(f"Found {len(csv_files)} CSV files in {input_dir}")

        return sorted(csv_files)

    def process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single CSV file through the complete pipeline.

        Args:
            file_path: Path to CSV file

        Returns:
            Processing results dictionary
        """
        self.logger.info(f"Processing file: {file_path.name}")

        results = {
            'file_path': str(file_path),
            'success': False,
            'error': None,
            'intermediate_rows': 0,
            'tiller_rows': 0,
            'intermediate_data': None,
            'tiller_data': None
        }

        # --- НАЧАЛО ДОБАВЛЯЕМОГО КОДА ---
        # Получаем конфигурацию для всех возможных источников из config.yaml
        source_converters_config = self.config.get('source_converters', {})
        if not source_converters_config:
            self.logger.error("No 'source_converters' defined in the configuration. Cannot process files.")
            results['error'] = "No source converter configurations found."
            return results

        # Простая эвристика для определения типа источника по имени файла.
        # Если у тебя будут другие банки, ты можешь расширить эту логику.
        detected_source_type = None
        parent_dir_name = file_path.parent.name.lower()

        for source_type_key in source_converters_config.keys():
            if parent_dir_name == source_type_key.lower():
                detected_source_type = source_type_key
        if not detected_source_type:
            self.logger.warning(f"Could not determine source type for file '{file_path.name}'. "
                                f"Parent directory '{parent_dir_name}' does not match any known source types.")

        for source_type, config_params in source_converters_config.items():
            if source_type.lower() in file_path.name.lower():
                detected_source_type = source_type
                break

        if not detected_source_type:
            self.logger.warning(f"Could not determine source type for file '{file_path.name}'. Skipping.")
            results['error'] = "Could not determine source type."
            return results

        source_config_params = source_converters_config.get(detected_source_type)
        if not source_config_params:
            self.logger.error(
                f"Configuration for detected source type '{detected_source_type}' is missing in config.yaml. Skipping file: {file_path.name}")
            results['error'] = f"Configuration for '{detected_source_type}' not found."
            return results

        source_schema_name = source_config_params.get('source_schema')
        mapping_name = source_config_params.get('mapping')

        if not source_schema_name or not mapping_name:
            self.logger.error(
                f"Incomplete configuration for source '{detected_source_type}'. Missing 'source_schema' or 'mapping'. Skipping file: {file_path.name}")
            results['error'] = f"Incomplete configuration for '{detected_source_type}'."
            return results

        # Инициализируем GenericSourceConverter для текущего файла
        current_source_converter = GenericSourceConverter(
            schema_loader=self.schema_loader,
            bank_type=parent_dir_name,
            source_schema_name=source_schema_name,
            mapping_rules_name=mapping_name
        )
        # --- КОНЕЦ ДОБАВЛЯЕМОГО КОДА ---

        try:
            # Step 1: Convert source to intermediate
            self.logger.info("Step 1: Converting source to intermediate format")
            # intermediate_df = self.source_converter.process_file(str(file_path))
            intermediate_df = current_source_converter.process_file(str(file_path))

            if len(intermediate_df) == 0:
                self.logger.warning("No data produced in intermediate format")
                return results

            results['intermediate_rows'] = len(intermediate_df)
            results['intermediate_data'] = intermediate_df

            # Step 2: Convert intermediate to Tiller
            self.logger.info("Step 2: Converting intermediate to Tiller format")
            tiller_df = self.target_converter.transform_to_target(intermediate_df)

            results['tiller_rows'] = len(tiller_df)
            results['tiller_data'] = tiller_df
            results['success'] = True

            self.logger.info(f"Successfully processed {file_path.name}: "
                             f"{results['intermediate_rows']} -> {results['tiller_rows']} transactions")

        except Exception as e:
            error_msg = f"Failed to process {file_path.name}: {e}"
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
        tiller_dfs = []

        for result in all_results:
            if result['success'] and result['intermediate_data'] is not None:
                intermediate_dfs.append(result['intermediate_data'])
            if result['success'] and result['tiller_data'] is not None:
                tiller_dfs.append(result['tiller_data'])

        if not intermediate_dfs and not tiller_dfs:
            self.logger.warning("No data to save")
            return

        # Combine DataFrames
        if intermediate_dfs:
            combined_intermediate = pd.concat(intermediate_dfs, ignore_index=True)
            self._save_intermediate_output(combined_intermediate)

        if tiller_dfs:
            combined_tiller = pd.concat(tiller_dfs, ignore_index=True)
            self._save_tiller_output(combined_tiller)

    def _save_intermediate_output(self, df: pd.DataFrame) -> None:
        """Save intermediate format output."""
        output_config = self.config.get_output_config()
        intermediate_config = output_config.get('intermediate_format', {})

        destination = intermediate_config.get('destination', 'file')

        if destination in ['file', 'both']:
            file_path = intermediate_config.get('file_path', 'output/intermediate_transactions.csv')
            df.to_csv(file_path, index=False, encoding='utf-8')
            self.logger.info(f"Saved intermediate data to: {file_path}")

        if destination in ['console', 'both']:
            print("\n" + "=" * 80)
            print("INTERMEDIATE FORMAT DATA:")
            print("=" * 80)
            print(df.to_string(index=False))
            print("=" * 80)

    def _save_tiller_output(self, df: pd.DataFrame) -> None:
        """Save Tiller format output."""
        output_config = self.config.get_output_config()
        tiller_config = output_config.get('tiller_format', {})

        destination = tiller_config.get('destination', 'both')

        if destination in ['file', 'both']:
            file_path = tiller_config.get('file_path', 'output/tiller_transactions.csv')
            self.target_converter.save_to_csv(df, file_path, output_config)

        if destination in ['console', 'both']:
            console_limit = tiller_config.get('console_limit', 50)
            formatted_output = self.target_converter.format_for_console(df, console_limit)
            print("\n" + "=" * 80)
            print("TILLER FORMAT DATA (Ready for copy-paste):")
            print("=" * 80)
            print(formatted_output)
            print("=" * 80)

    def run(self, input_dir: str) -> bool:
        """
        Run the complete ETL pipeline.

        Args:
            input_dir: Directory containing CSV files to process

        Returns:
            True if processing was successful, False otherwise
        """
        self.logger.info(f"Starting ETL pipeline for directory: {input_dir}")

        try:
            # Find CSV files
            csv_files = self.find_csv_files(input_dir)

            if not csv_files:
                self.logger.error("No CSV files found to process")
                return False

            # Process all files
            all_results = []
            successful_files = 0

            for csv_file in csv_files:
                result = self.process_single_file(csv_file)
                all_results.append(result)

                if result['success']:
                    successful_files += 1

            # Save outputs
            if successful_files > 0:
                self.save_outputs(all_results)

            # Summary
            total_files = len(csv_files)
            failed_files = total_files - successful_files

            self.logger.info(f"ETL Pipeline completed: {successful_files}/{total_files} files processed successfully")

            if failed_files > 0:
                self.logger.warning(f"{failed_files} files failed to process")

                # Log failed files
                for result in all_results:
                    if not result['success']:
                        self.logger.error(f"Failed: {result['file_path']} - {result['error']}")

            return successful_files > 0

        except Exception as e:
            self.logger.error(f"ETL pipeline failed: {e}")
            return False


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Bank to Tiller ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --input-dir ./data
  python main.py --input-dir /path/to/bank/exports --config custom_config.yaml
        """
    )

    parser.add_argument(
        '--input-dir',
        required=True,
        help='Directory containing bank CSV files to process'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate files and configuration without processing'
    )

    return parser


def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    try:
        # Initialize pipeline
        pipeline = ETLPipeline(config_path=args.config)

        if args.dry_run:
            print("DRY RUN: Validating configuration and finding files...")
            csv_files = pipeline.find_csv_files(args.input_dir)
            print(f"Found {len(csv_files)} CSV files:")
            for file_path in csv_files:
                print(f"  - {file_path}")
            print("Configuration validation passed. Use without --dry-run to process files.")
            return 0

        # Run pipeline
        success = pipeline.run(args.input_dir)

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())