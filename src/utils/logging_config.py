"""
Logging configuration utilities.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any


def setup_logging(config: Dict[str, Any]) -> None:
    """
    Setup logging configuration based on config dictionary.

    Args:
        config: Logging configuration dictionary
    """
    # Get logging level
    level_str = config.get('level', 'INFO')
    level = getattr(logging, level_str.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if config.get('console', True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    file_config = config.get('file', {})
    if file_config.get('enabled', False):
        file_path = file_config.get('path', 'logs/etl_pipeline.log')

        # Ensure log directory exists
        log_path = Path(file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Parse max_size (e.g., "10MB" -> 10*1024*1024)
        max_size_str = file_config.get('max_size', '10MB')
        max_size = parse_size(max_size_str)

        backup_count = file_config.get('backup_count', 5)

        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Log the setup completion
    logger = logging.getLogger(__name__)
    logger.info("Logging configuration setup completed")


def parse_size(size_str: str) -> int:
    """
    Parse size string to bytes.

    Args:
        size_str: Size string like "10MB", "1GB", "500KB"

    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()

    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        # Assume bytes if no unit specified
        return int(size_str)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging functionality to other classes.
    """

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_dataframe_info(logger: logging.Logger, df, description: str = "DataFrame") -> None:
    """
    Log basic information about a DataFrame.

    Args:
        logger: Logger instance
        df: pandas DataFrame
        description: Description of the DataFrame
    """
    logger.info(f"{description} shape: {df.shape}")
    logger.debug(f"{description} columns: {list(df.columns)}")
    if hasattr(df, 'memory_usage'):
        memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
        logger.debug(f"{description} memory usage: {memory_mb:.2f} MB")


def log_processing_step(logger: logging.Logger, step_name: str, input_count: int,
                        output_count: int) -> None:
    """
    Log information about a processing step.

    Args:
        logger: Logger instance
        step_name: Name of the processing step
        input_count: Number of input records
        output_count: Number of output records
    """
    logger.info(f"{step_name}: {input_count} -> {output_count} records "
                f"({output_count - input_count:+d})")

    if input_count > 0:
        percentage = (output_count / input_count) * 100
        logger.debug(f"{step_name}: {percentage:.1f}% of records retained")