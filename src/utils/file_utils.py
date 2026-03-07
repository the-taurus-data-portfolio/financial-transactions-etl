"""
File system utilities for locating and processing input files.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from core.interfaces import SourceArchiver


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


class LocalFileArchiver(SourceArchiver):
    """
    Archives processed files by moving them to a local archive directory.
    """

    def __init__(self, archive_dir: str, add_timestamp: bool = False,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the archiver.

        Args:
            archive_dir: Directory to move files to
            add_timestamp: Whether to add timestamp to archived filenames
            logger: Optional logger instance
        """
        self.archive_dir = Path(archive_dir)
        self.add_timestamp = add_timestamp
        self.logger = logger or logging.getLogger(__name__)

    def archive(self, file_identifiers: List[Path]) -> bool:
        """
        Move files to archive directory.

        Args:
            file_identifiers: List of Path objects to move

        Returns:
            True if all files were successfully archived, False otherwise
        """
        if not file_identifiers:
            self.logger.info("No local files to archive")
            return True

        try:
            # Ensure archive directory exists
            self.archive_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success_count = 0

            for source_path in file_identifiers:
                if not isinstance(source_path, Path):
                    source_path = Path(source_path)

                if not source_path.exists():
                    self.logger.warning(f"File not found for archiving: {source_path}")
                    continue

                target_filename = source_path.name
                if self.add_timestamp:
                    name_parts = source_path.name.rsplit('.', 1)
                    if len(name_parts) > 1:
                        target_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
                    else:
                        target_filename = f"{source_path.name}_{timestamp}"

                target_path = self.archive_dir / target_filename

                # Move file (overwrites if already exists and add_timestamp is False)
                shutil.move(str(source_path), str(target_path))
                self.logger.info(f"Archived: {source_path.name} -> {target_path}")
                success_count += 1

            return success_count == len(file_identifiers)

        except Exception as e:
            self.logger.error(f"Failed to archive local files: {e}")
            return False
