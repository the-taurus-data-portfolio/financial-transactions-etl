"""
Manager for target converter initialization and selection.

Handles loading and configuring target converters based on configuration.
Currently supports Tiller converter; can be extended for other targets.
"""

import logging
from typing import Optional

from core.config_manager import ConfigManager
from core.schema_loader import YamlSchemaLoader


class TargetConverterManager:
    """
    Manages target converter initialization and selection.
    """

    # Map of target names to converter classes
    CONVERTERS = {}

    def __init__(self, config: ConfigManager, schema_loader: YamlSchemaLoader,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the target converter manager.

        Args:
            config: ConfigManager instance
            schema_loader: YamlSchemaLoader instance
            logger: Optional logger instance
        """
        self.config = config
        self.schema_loader = schema_loader
        self.logger = logger or logging.getLogger(__name__)
        self._converters = {}

    def initialize_converters(self) -> None:
        """
        Initialize all enabled target converters from configuration.

        Raises:
            ValueError: If target_converters config is missing or invalid
        """
        target_converters_config = self.config.get('target_converters', {})
        if not target_converters_config:
            raise ValueError("No 'target_converters' defined in configuration")

        for target_name, target_config in target_converters_config.items():
            try:
                converter = self._create_converter(target_name, target_config)
                if converter:
                    self._converters[target_name] = converter
                    self.logger.info(f"Initialized target converter: {target_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize target converter '{target_name}': {e}")
                raise

    def _create_converter(self, target_name: str, target_config: dict):
        """
        Create a converter instance for the given target.

        Args:
            target_name: Name of the target (e.g., 'tiller')
            target_config: Configuration for the target

        Returns:
            Initialized converter instance or None if target is not supported
        """
        if target_name == 'tiller':
            from converters.tiller_converter import TillerConverter
            accounts_file = target_config.get('accounts_file', 'config/tiller/accounts.yaml')
            deduplication_config = target_config.get('deduplication', {})
            return TillerConverter(
                self.schema_loader,
                tiller_config=deduplication_config,
                accounts_file=accounts_file
            )
        else:
            self.logger.warning(f"Unknown target converter: {target_name}")
            return None

    def get_converter(self, target_name: str):
        """
        Get initialized converter for a target.

        Args:
            target_name: Name of the target (e.g., 'tiller')

        Returns:
            Converter instance or None if not initialized

        Raises:
            ValueError: If target is not initialized
        """
        if target_name not in self._converters:
            raise ValueError(f"Target converter '{target_name}' not initialized")
        return self._converters[target_name]

    def get_default_converter(self):
        """
        Get the default (first) target converter.

        Returns:
            Converter instance

        Raises:
            ValueError: If no converters are initialized
        """
        if not self._converters:
            raise ValueError("No target converters initialized")
        return next(iter(self._converters.values()))

    def get_default_target_name(self) -> str:
        """
        Get the name of the default target.

        Returns:
            Target name (e.g., 'tiller')

        Raises:
            ValueError: If no converters are initialized
        """
        if not self._converters:
            raise ValueError("No target converters initialized")
        return next(iter(self._converters.keys()))

    def list_targets(self) -> list:
        """
        List names of all initialized target converters.

        Returns:
            List of target names
        """
        return list(self._converters.keys())
