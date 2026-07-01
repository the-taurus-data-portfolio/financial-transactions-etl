"""
Abstract base classes defining interfaces for data converters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import io

import pandas as pd


class SourceProvider(ABC):
    """
    Abstract base class for providing access to source data files.
    """

    @abstractmethod
    def list_files(self) -> List[Dict[str, Any]]:
        """
        List metadata for available files.

        Returns:
            List of dictionaries containing file metadata (e.g., name, identifier)
        """
        pass

    @abstractmethod
    def get_file_content(self, identifier: Any) -> io.BytesIO:
        """
        Get the content of a file.

        Args:
            identifier: Implementation-specific file identifier (e.g., path, ID)

        Returns:
            File content as BytesIO buffer
        """
        pass


class SourceConverter(ABC):
    """
    Abstract base class for converting data from bank source format
    to intermediate format.
    """

    @abstractmethod
    def load_source_data(self, file_content: io.BytesIO) -> pd.DataFrame:
        """
        Load data from source bank CSV content.

        Args:
            file_content: BytesIO buffer with CSV content

        Returns:
            DataFrame with loaded source data

        Raises:
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

    def extract_header(self, file_content: io.BytesIO) -> Dict[str, Any]:
        """
        Extract metadata from file header rows before the main CSV parse.

        Subclasses override this to read bank-specific header rows (e.g. IBAN,
        currency). The returned dict is injected as constant columns into the
        loaded DataFrame. Default: no-op, returns empty dict.
        """
        return {}

    def extract_footer(self, file_content: io.BytesIO) -> Dict[str, Any]:
        """
        Extract metadata from file footer rows after the main CSV parse.

        Reserved for future use (e.g. closing balances). Default: no-op.
        """
        return {}

    def post_process(self, intermediate_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply post-processing after standard field mapping.

        Subclasses override this to populate fields that cannot be expressed as
        simple YAML mappings (e.g. extracting OtherAccountName from Narrative).
        Receives both DataFrames so any source column is accessible even if not
        mapped to the intermediate schema. Default: no-op, returns intermediate_df.
        """
        return intermediate_df

    @abstractmethod
    def save_output(self, df: pd.DataFrame, config) -> None:
        """
        Save intermediate format output to file and/or console.

        Args:
            df: DataFrame in intermediate format
            config: ConfigManager instance
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

    @abstractmethod
    def save_output(self, df: pd.DataFrame, config, target_name: str = 'target') -> None:
        """
        Save target format output to file and/or console.

        Args:
            df: DataFrame in target format
            config: ConfigManager instance
            target_name: Name of the target system for headers
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


class SourceArchiver(ABC):
    """
    Abstract base class for archiving source data files after processing.
    """

    @abstractmethod
    def archive(self, file_identifiers: List[Any]) -> bool:
        """
        Archive processed source files.

        Args:
            file_identifiers: List of identifiers to files to archive

        Returns:
            True if archiving was successful, False otherwise
        """
        pass
