"""
File system utilities for locating and processing input files.
"""

import logging
from pathlib import Path
from typing import List, Optional


def get_input_files(input_dir: str, supported_extensions: List[str],
                    logger: Optional[logging.Logger] = None) -> List[Path]:
    """
    Find all files in the input directory matching supported extensions.

    Args:
        input_dir: Directory to search for files
        supported_extensions: List of file extensions to match (e.g., ['.csv', '.CSV'])
        logger: Optional logger instance for debug/info messages

    Returns:
        Sorted list of matching file paths

    Raises:
        FileNotFoundError: If input directory does not exist
        ValueError: If input path is not a directory
    """
    logger = logger or logging.getLogger(__name__)

    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if not input_path.is_dir():
        raise ValueError(f"Input path is not a directory: {input_dir}")

    # Find all files matching supported extensions
    input_files = []
    for ext in supported_extensions:
        input_files.extend(input_path.glob(f"*{ext}"))

    if not input_files:
        logger.warning(f"No files matching extensions {supported_extensions} found in {input_dir}")
    else:
        logger.info(f"Found {len(input_files)} files matching {supported_extensions} in {input_dir}")

    return sorted(input_files)
