"""
Utility functions for CSV file operations.
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional


def read_csv_header(file_path: Path, logger: Optional[logging.Logger] = None) -> Optional[List[str]]:
    """
    Read CSV header row from a file, auto-detecting delimiter.

    Tries delimiters in order: semicolon, comma, tab.

    Args:
        file_path: Path to CSV file
        logger: Optional logger instance for debug messages

    Returns:
        List of header column names or None if reading fails
    """
    logger = logger or logging.getLogger(__name__)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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
    except Exception as e:
        logger.debug(f"Error reading CSV header from {file_path.name}: {e}")
        return None


def detect_csv_delimiter(file_path: Path, logger: Optional[logging.Logger] = None) -> str:
    """
    Detect the CSV delimiter used in a file.

    Tries delimiters in order: semicolon, comma, tab.

    Args:
        file_path: Path to CSV file
        logger: Optional logger instance

    Returns:
        The detected delimiter (default: semicolon)
    """
    logger = logger or logging.getLogger(__name__)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
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
    except Exception as e:
        logger.debug(f"Error detecting CSV delimiter: {e}")

    logger.debug("Could not detect delimiter, using default: semicolon")
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
        import pyperclip
        # Format as TSV without header for easy pasting into Google Sheets
        tsv_data = df.to_csv(sep='\t', index=False, header=False)
        pyperclip.copy(tsv_data)
        logger.info("Successfully copied transaction data to clipboard (TSV format, no header)")
        return True
    except ImportError:
        logger.error("Failed to copy to clipboard: 'pyperclip' module not found")
        return False
    except Exception as e:
        logger.error(f"Failed to copy to clipboard: {e}")
        return False
