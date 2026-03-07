"""
Utility functions for CSV file operations.
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional, Union
import io
import pyperclip


def read_csv_header(source: Union[Path, io.BytesIO], logger: Optional[logging.Logger] = None) -> Optional[List[str]]:
    """
    Read CSV header row from a file path or buffer, auto-detecting delimiter.

    Tries delimiters in order: semicolon, comma, tab.

    Args:
        source: Path to CSV file or BytesIO buffer
        logger: Optional logger instance for debug messages

    Returns:
        List of header column names or None if reading fails
    """
    logger = logger or logging.getLogger(__name__)

    try:
        if isinstance(source, Path):
            with open(source, 'r', encoding='utf-8') as f:
                return _read_header_from_file_object(f, logger)
        else:
            # Handle BytesIO
            source.seek(0)
            # Use TextIOWrapper to read BytesIO as text
            wrapper = io.TextIOWrapper(source, encoding='utf-8', newline='')
            header = _read_header_from_file_object(wrapper, logger)
            # Detach to prevent wrapper from closing the underlying buffer
            wrapper.detach()
            return header
    except Exception as e:
        logger.debug(f"Error reading CSV header: {e}")
        return None


def _read_header_from_file_object(f, logger):
    """Internal helper to read header from a file-like object."""
    for delimiter in [';', ',', '\t']:
        f.seek(0)
        try:
            reader = csv.reader(f, delimiter=delimiter)
            header_row = next(reader, None)
            if header_row:
                return [col.strip().strip('"') for col in header_row]
        except Exception:
            continue
    return None


def detect_csv_delimiter(source: Union[Path, io.BytesIO], logger: Optional[logging.Logger] = None) -> str:
    """
    Detect the CSV delimiter used in a file path or buffer.

    Tries delimiters in order: semicolon, comma, tab.

    Args:
        source: Path to CSV file or BytesIO buffer
        logger: Optional logger instance

    Returns:
        The detected delimiter (default: semicolon)
    """
    logger = logger or logging.getLogger(__name__)

    try:
        if isinstance(source, Path):
            with open(source, 'r', encoding='utf-8') as f:
                return _detect_delimiter_from_file_object(f, logger)
        else:
            source.seek(0)
            wrapper = io.TextIOWrapper(source, encoding='utf-8', newline='')
            delimiter = _detect_delimiter_from_file_object(wrapper, logger)
            wrapper.detach()
            return delimiter
    except Exception as e:
        logger.debug(f"Error detecting CSV delimiter: {e}")

    return ';'


def _detect_delimiter_from_file_object(f, logger):
    """Internal helper to detect delimiter from a file-like object."""
    for delimiter in [';', ',', '\t']:
        f.seek(0)
        try:
            reader = csv.reader(f, delimiter=delimiter)
            header_row = next(reader, None)
            if header_row and len(header_row) > 1:
                logger.debug(f"Detected CSV delimiter: {repr(delimiter)}")
                return delimiter
        except Exception:
            continue
    return ';'


def copy_df_to_clipboard(df: 'pd.DataFrame', logger: Optional[logging.Logger] = None) -> bool:
    """
    Copy DataFrame content to clipboard in TSV format without header.

    Args:
        df: DataFrame to copy
        logger: Optional logger instance

    Returns:
        True if copy was successful, False otherwise
    """
    logger = logger or logging.getLogger(__name__)

    try:
        # Format as TSV without header for easy pasting into Google Sheets
        tsv_data = df.to_csv(sep='\t', index=False, header=False)
        pyperclip.copy(tsv_data)
        logger.info("Successfully copied transaction data to clipboard (TSV format, no header)")
        return True
    except Exception as e:
        logger.error(f"Failed to copy to clipboard: {e}")
        return False
