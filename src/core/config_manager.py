"""
Configuration management for the ETL pipeline.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import yaml


class ConfigManager:
    """
    Manages configuration loading and access for the ETL pipeline.
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

        self.load_config()

    def load_config(self) -> None:
        """
        Load configuration from YAML file.

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)

            self.logger.debug(f"Configuration loaded from {self.config_path}")

        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse configuration YAML: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading configuration: {e}")
            raise

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path.

        Args:
            key_path: Dot-separated path to configuration value (e.g., 'logging.level')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_logging_config(self) -> Dict[str, Any]:
        """
        Get logging configuration.

        Returns:
            Logging configuration dictionary
        """
        return self.get('logging', {
            'level': 'INFO',
            'console': True,
            'file': {'enabled': True, 'path': 'logs/etl_pipeline.log'}
        })

    def get_google_auth_config(self) -> Dict[str, Any]:
        """
        Get Google authentication configuration.

        Returns:
            Google auth configuration dictionary
        """
        return self.get('google_auth', {
            'credentials_file': 'config/credentials/test-spreadsheet-credentials.json'
        })

    def get_output_config(self) -> Dict[str, Any]:
        """
        Get output configuration.

        Returns:
            Output configuration dictionary
        """
        return self.get('output', {
            'intermediate_format': {
                'destination': 'file',
                'file_path': 'output/intermediate_transactions.csv'
            },
            'tiller_format': {
                'destination': 'both',
                'file_path': 'output/tiller_transactions.csv',
                'console_limit': 50
            }
        })

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration.

        Returns:
            Processing configuration dictionary
        """
        return self.get('processing', {
            'auto_detect_bank': False,
            'default_bank_type': 'swedbank',
            'strict_mode': False,
            'skip_invalid_rows': True,
            'validate_schemas': True,
            'validate_amounts': True,
            'max_amount_threshold': 1000000,
            'copy_to_clipboard': True
        })

    def get_file_config(self) -> Dict[str, Any]:
        """
        Get file processing configuration.

        Returns:
            File configuration dictionary
        """
        return self.get('files', {
            'supported_extensions': ['.csv', '.CSV'],
            'encoding': 'utf-8',
            'csv_options': {
                'skip_blank_lines': True,
                'strip_whitespace': True
            }
        })

    def get_paths_config(self) -> Dict[str, Any]:
        """
        Get paths configuration.

        Returns:
            Paths configuration dictionary
        """
        return self.get('paths', {
            'schemas_dir': 'schemas',
            'mappings_dir': 'mappings',
            'output_dir': 'output',
            'logs_dir': 'logs'
        })

    def is_strict_mode(self) -> bool:
        """
        Check if strict mode is enabled.

        Returns:
            True if strict mode is enabled
        """
        return self.get('processing.strict_mode', False)

    def should_skip_invalid_rows(self) -> bool:
        """
        Check if invalid rows should be skipped.

        Returns:
            True if invalid rows should be skipped
        """
        return self.get('processing.skip_invalid_rows', True)

    def should_validate_schemas(self) -> bool:
        """
        Check if schema validation is enabled.

        Returns:
            True if schema validation is enabled
        """
        return self.get('processing.validate_schemas', True)

    def get_max_amount_threshold(self) -> float:
        """
        Get maximum amount threshold for validation.

        Returns:
            Maximum amount threshold
        """
        return self.get('processing.max_amount_threshold', 1000000.0)

    def get_supported_extensions(self) -> list:
        """
        Get list of supported file extensions.

        Returns:
            List of supported extensions
        """
        return self.get('files.supported_extensions', ['.csv', '.CSV'])

    def get_default_encoding(self) -> str:
        """
        Get default file encoding.

        Returns:
            Default encoding string
        """
        return self.get('files.encoding', 'utf-8')

    def ensure_directories(self) -> None:
        """
        Ensure all required directories exist.
        """
        paths = self.get_paths_config()

        for dir_key, dir_path in paths.items():
            path = Path(dir_path)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {path}")

        # Also ensure local archive directory if local archiving is enabled
        archiving_config = self.get('archiving', {})
        if archiving_config.get('enabled', False) and archiving_config.get('type') == 'local':
            archive_dir = archiving_config.get('local', {}).get('archive_dir', 'data/archive')
            archive_path = Path(archive_dir)
            if not archive_path.exists():
                archive_path.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created local archive directory: {archive_path}")

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"ConfigManager(config_path={self.config_path})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"ConfigManager(config_path={self.config_path}, loaded={bool(self.config)})"
