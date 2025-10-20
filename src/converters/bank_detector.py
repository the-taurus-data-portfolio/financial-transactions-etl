"""
Bank detection utilities for identifying bank types from CSV headers.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.config_manager import ConfigManager
from utils import csv_utils


class BankDetector:
    """
    Detects bank type from CSV header by matching against known signatures.
    """

    def __init__(self, config: ConfigManager, logger: Optional[logging.Logger] = None):
        """
        Initialize the bank detector.

        Args:
            config: ConfigManager instance
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.bank_header_signatures = {}  # Dict mapping header tuples to bank types

        self._load_bank_header_signatures()

    def _load_bank_header_signatures(self) -> None:
        """Load header signatures from sample files for bank detection."""
        try:
            source_converters_config = self.config.get('source_converters', {})
            if not source_converters_config:
                self.logger.warning("No source_converters defined in configuration")
                return

            for bank_type, config_params in source_converters_config.items():
                sample_files = config_params.get('sample_files', [])
                if not sample_files:
                    self.logger.warning(
                        f"No sample files configured for bank type '{bank_type}'. "
                        "Header-based detection will not work for this bank."
                    )
                    continue

                for sample_file_path in sample_files:
                    try:
                        file_path = Path(sample_file_path)
                        if not file_path.exists():
                            self.logger.warning(
                                f"Sample file not found for bank '{bank_type}': {sample_file_path}"
                            )
                            continue

                        header_row = csv_utils.read_csv_header(file_path, self.logger)
                        if header_row:
                            header_tuple = tuple(header_row)
                            self.bank_header_signatures[header_tuple] = bank_type
                            self.logger.debug(
                                f"Loaded header signature for bank '{bank_type}' "
                                f"from {file_path.name}"
                            )

                    except Exception as e:
                        self.logger.warning(
                            f"Failed to load header from sample file '{sample_file_path}': {e}"
                        )
                        continue

            if self.bank_header_signatures:
                self.logger.info(
                    f"Loaded {len(self.bank_header_signatures)} header signatures "
                    f"for bank detection"
                )
            else:
                self.logger.warning("No header signatures loaded. Bank detection may fail.")

        except Exception as e:
            self.logger.error(f"Error loading bank header signatures: {e}")

    def detect_bank_from_header(self, file_path: Path) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect bank type by matching CSV header row against known signatures.

        Args:
            file_path: Path to the CSV file

        Returns:
            Tuple of (detected_bank_type, matched_sample_file_path) or (None, None) if detection fails
        """
        try:
            if not self.bank_header_signatures:
                self.logger.warning("No bank header signatures loaded for detection")
                return None, None

            header_row = csv_utils.read_csv_header(file_path, self.logger)
            if not header_row:
                self.logger.warning(f"Could not read CSV header from {file_path.name}")
                return None, None

            header_tuple = tuple(header_row)

            if header_tuple in self.bank_header_signatures:
                bank_type = self.bank_header_signatures[header_tuple]
                # Find which sample file this header came from
                matched_sample = self._find_sample_for_bank(bank_type, header_tuple)
                self.logger.debug(
                    f"Detected bank type '{bank_type}' for file {file_path.name} "
                    f"via header matching"
                )
                return bank_type, matched_sample

            self.logger.warning(
                f"Could not auto-detect bank type for {file_path.name}. "
                "Header does not match any known signatures."
            )
            return None, None

        except Exception as e:
            self.logger.error(f"Error detecting bank type for {file_path.name}: {e}")
            return None, None

    def _find_sample_for_bank(self, bank_type: str, header_tuple: Tuple[str, ...]) -> Optional[str]:
        """Find which sample file matches this header."""
        source_converters_config = self.config.get('source_converters', {})
        config = source_converters_config.get(bank_type, {})
        sample_files = config.get('sample_files', [])

        for sample_file in sample_files:
            sample_header = csv_utils.read_csv_header(Path(sample_file), self.logger)
            if sample_header and tuple(sample_header) == header_tuple:
                return sample_file

        return None

    def get_primary_sample_file(self, bank_type: str) -> Optional[str]:
        """
        Get the primary (first) sample file for a bank type.

        Args:
            bank_type: The bank type to get sample file for

        Returns:
            Path to primary sample file or None
        """
        source_converters_config = self.config.get('source_converters', {})
        config = source_converters_config.get(bank_type, {})
        sample_files = config.get('sample_files', [])
        return sample_files[0] if sample_files else None
