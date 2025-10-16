"""
Schema and mapping loader implementation.
"""

import yaml
import os
import logging
from typing import Dict, Any, List
from pathlib import Path

from .interfaces import SchemaLoader


class YamlSchemaLoader(SchemaLoader):
    """
    Implementation of SchemaLoader for YAML files.
    """

    def __init__(self, schemas_dir: str, mappings_dir: str):
        """
        Initialize schema loader.

        Args:
            schemas_dir: Directory containing schema files
            mappings_dir: Directory containing mapping files
        """
        self.schemas_dir = Path(schemas_dir)
        self.mappings_dir = Path(mappings_dir)
        self.logger = logging.getLogger(__name__)

        # Validate directories exist
        if not self.schemas_dir.exists():
            raise FileNotFoundError(f"Schemas directory not found: {schemas_dir}")
        if not self.mappings_dir.exists():
            raise FileNotFoundError(f"Mappings directory not found: {mappings_dir}")

    def load_schema(self, schema_file: str) -> Dict[str, Any]:
        """
        Load schema from YAML file.

        Args:
            schema_file: Schema filename (e.g., 'swedbank_source.yaml')

        Returns:
            Schema dictionary

        Raises:
            FileNotFoundError: If schema file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        schema_path = self.schemas_dir / schema_file

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        try:
            with open(schema_path, 'r', encoding='utf-8') as file:
                schema = yaml.safe_load(file)

            self.logger.debug(f"Loaded schema from {schema_path}")
            return schema

        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML schema {schema_path}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading schema {schema_path}: {e}")
            raise

    def load_mapping(self, mapping_file: str) -> Dict[str, Any]:
        """
        Load mapping rules from YAML file.

        Args:
            mapping_file: Mapping filename (e.g., 'swedbank_to_intermediate.yaml')

        Returns:
            Mapping rules dictionary

        Raises:
            FileNotFoundError: If mapping file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        mapping_path = self.mappings_dir / mapping_file

        if not mapping_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

        try:
            with open(mapping_path, 'r', encoding='utf-8') as file:
                mapping = yaml.safe_load(file)

            self.logger.debug(f"Loaded mapping from {mapping_path}")
            return mapping

        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML mapping {mapping_path}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading mapping {mapping_path}: {e}")
            raise

    def validate_schema_compatibility(self, source_schema: Dict[str, Any],
                                      target_schema: Dict[str, Any]) -> bool:
        """
        Validate that source and target schemas are compatible.

        Args:
            source_schema: Source schema dictionary
            target_schema: Target schema dictionary

        Returns:
            True if compatible, False otherwise
        """
        try:
            # Basic validation - check if required keys exist
            source_fields = source_schema.get('fields', [])
            target_fields = target_schema.get('fields', [])

            if not source_fields or not target_fields:
                self.logger.warning("Schema validation: Missing 'fields' section")
                return False

            # Validate field structures
            for field in source_fields:
                if not isinstance(field, dict) or 'name' not in field:
                    self.logger.error(f"Invalid source field structure: {field}")
                    return False

            for field in target_fields:
                if not isinstance(field, dict) or 'name' not in field:
                    self.logger.error(f"Invalid target field structure: {field}")
                    return False

            self.logger.debug("Schema compatibility validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Schema compatibility validation failed: {e}")
            return False

    def get_field_aliases(self, schema: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract field name to alias mapping from schema.

        Args:
            schema: Schema dictionary

        Returns:
            Dictionary mapping field names to aliases
        """
        aliases = {}
        fields = schema.get('fields', [])

        for field in fields:
            name = field.get('name')
            alias = field.get('alias')
            if name and alias:
                aliases[name] = alias

        return aliases

    def get_field_types(self, schema: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract field name to type mapping from schema.

        Args:
            schema: Schema dictionary

        Returns:
            Dictionary mapping field names to types
        """
        types = {}
        fields = schema.get('fields', [])

        for field in fields:
            name = field.get('name')
            field_type = field.get('type')
            if name and field_type:
                types[name] = field_type

        return types

    def list_available_schemas(self) -> List[str]:
        """
        List all available schema files.

        Returns:
            List of schema filenames
        """
        return [f.name for f in self.schemas_dir.glob('*.yaml')]

    def list_available_mappings(self) -> List[str]:
        """
        List all available mapping files.

        Returns:
            List of mapping filenames
        """
        return [f.name for f in self.mappings_dir.glob('*.yaml')]