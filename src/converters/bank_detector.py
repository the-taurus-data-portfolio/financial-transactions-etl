"""
Bank detection utilities for identifying bank types from CSV headers.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
import io

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
        # {detection_skip_rows: {header_tuple: bank_type}}
        self._signatures_by_skip: Dict[int, Dict[tuple, str]] = {}

        self._load_bank_header_signatures()

    def _load_bank_header_signatures(self) -> None:
        """Load header signatures from sample files for bank detection."""
        try:
            source_converters_config = self.config.get('source_converters', {})
            if not source_converters_config:
                self.logger.warning("No source_converters defined in configuration")
                return

            for bank_type, config_params in source_converters_config.items():
                detection_skip_rows = config_params.get('detection_header_row', 0)
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

                        header_row = csv_utils.read_csv_header(
                            file_path, self.logger, skip_rows=detection_skip_rows
                        )
                        if header_row:
                            header_tuple = tuple(header_row)
                            if detection_skip_rows not in self._signatures_by_skip:
                                self._signatures_by_skip[detection_skip_rows] = {}
                            self._signatures_by_skip[detection_skip_rows][header_tuple] = bank_type
                            self.logger.debug(
                                f"Loaded header signature for bank '{bank_type}' "
                                f"from {file_path.name} (detection_skip_rows={detection_skip_rows})"
                            )

                    except Exception as e:
                        self.logger.warning(
                            f"Failed to load header from sample file '{sample_file_path}': {e}"
                        )
                        continue

            total_signatures = sum(len(sigs) for sigs in self._signatures_by_skip.values())
            if self._signatures_by_skip:
                self.logger.info(
                    f"Loaded {total_signatures} header signatures for bank detection"
                )
            else:
                self.logger.warning("No header signatures loaded. Bank detection may fail.")

        except Exception as e:
            self.logger.error(f"Error loading bank header signatures: {e}")

    def detect_bank_from_header(self, source: Union[Path, io.BytesIO]) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect bank type by matching CSV header row against known signatures.

        Args:
            source: Path to the CSV file or BytesIO buffer

        Returns:
            Tuple of (detected_bank_type, matched_sample_file_path) or (None, None) if detection fails
        """
        try:
            if not self._signatures_by_skip:
                self.logger.warning("No bank header signatures loaded for detection")
                return None, None

            name = source.name if isinstance(source, Path) else "buffer"

            for skip_rows, signatures in sorted(self._signatures_by_skip.items()):
                header_row = csv_utils.read_csv_header(source, self.logger, skip_rows=skip_rows)
                if not header_row:
                    continue
                header_tuple = tuple(header_row)
                if header_tuple in signatures:
                    bank_type = signatures[header_tuple]
                    matched_sample = self._find_sample_for_bank(bank_type, header_tuple)
                    self.logger.debug(
                        f"Detected bank type '{bank_type}' for {name} "
                        f"via header matching (skip_rows={skip_rows})"
                    )
                    return bank_type, matched_sample

            self.logger.warning(
                f"Could not auto-detect bank type for {name}. "
                "Header does not match any known signatures."
            )
            return None, None

        except Exception as e:
            name = source.name if isinstance(source, Path) else "buffer"
            self.logger.error(f"Error detecting bank type for {name}: {e}")
            return None, None

    def _find_sample_for_bank(self, bank_type: str, header_tuple: Tuple[str, ...]) -> Optional[str]:
        """Find which sample file matches this header."""
        source_converters_config = self.config.get('source_converters', {})
        config = source_converters_config.get(bank_type, {})
        sample_files = config.get('sample_files', [])
        skip_rows = config.get('detection_header_row', 0)

        for sample_file in sample_files:
            sample_header = csv_utils.read_csv_header(Path(sample_file), self.logger, skip_rows=skip_rows)
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
