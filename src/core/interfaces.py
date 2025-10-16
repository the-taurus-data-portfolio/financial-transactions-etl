"""
Abstract base classes defining interfaces for data converters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

import pandas as pd


class SourceConverter(ABC):
    """
    Abstract base class for converting data from bank source format
    to intermediate format.
    """

    @abstractmethod
    def load_source_data(self, file_path: str) -> pd.DataFrame:
        """
        Load data from source bank CSV file.

        Args:
            file_path: Path to the source CSV file

        Returns:
            DataFrame with loaded source data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        pass

    @abstractmethod
    def validate_source_schema(self, df: pd.DataFrame) -> bool:
        """
        Validate that the source data matches expected schema.

        Args:
            df: DataFrame to validate

        Returns:
            True if schema is valid, False otherwise
        """
        pass

    @abstractmethod
    def filter_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply row filters based on mapping rules.

        Args:
            df: Input DataFrame

        Returns:
            Filtered DataFrame
        """
        pass

    @abstractmethod
    def transform_to_intermediate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform source data to intermediate format.

        Args:
            df: Source DataFrame

        Returns:
            DataFrame in intermediate format
        """
        pass

    @abstractmethod
    def get_bank_type(self) -> str:
        """
        Return the bank type this converter handles.

        Returns:
            Bank type identifier
        """
        pass


class TargetConverter(ABC):
    """
    Abstract base class for converting data from intermediate format
    to target system format.
    """

    @abstractmethod
    def load_intermediate_data(self, file_path: str) -> pd.DataFrame:
        """
        Load data from intermediate format CSV file.

        Args:
            file_path: Path to the intermediate CSV file

        Returns:
            DataFrame with intermediate data
        """
        pass

    @abstractmethod
    def validate_intermediate_schema(self, df: pd.DataFrame) -> bool:
        """
        Validate that the intermediate data matches expected schema.

        Args:
            df: DataFrame to validate

        Returns:
            True if schema is valid, False otherwise
        """
        pass

    @abstractmethod
    def transform_to_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform intermediate data to target format.

        Args:
            df: Intermediate DataFrame

        Returns:
            DataFrame in target format
        """
        pass

    @abstractmethod
    def get_target_type(self) -> str:
        """
        Return the target system type this converter handles.

        Returns:
            Target system identifier
        """
        pass


class SchemaLoader(ABC):
    """
    Abstract base class for loading and validating schemas.
    """

    @abstractmethod
    def load_schema(self, schema_path: str) -> Dict[str, Any]:
        """
        Load schema from YAML file.

        Args:
            schema_path: Path to schema file

        Returns:
            Schema dictionary
        """
        pass

    @abstractmethod
    def load_mapping(self, mapping_path: str) -> Dict[str, Any]:
        """
        Load mapping rules from YAML file.

        Args:
            mapping_path: Path to mapping file

        Returns:
            Mapping rules dictionary
        """
        pass

    @abstractmethod
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
        pass