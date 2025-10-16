# src/converters/swedbank_converter.py
"""
Swedbank CSV to intermediate format converter.
"""

import pandas as pd
import logging
from typing import Dict, Any, List
from pathlib import Path

from src.core.interfaces import SourceConverter
from src.core.schema_loader import YamlSchemaLoader
from src.utils.string_utils import (
    clean_string, anonymize_iban, convert_decimal_separator,
    parse_amount, apply_amount_sign, prefix_string
)
from src.utils.logging_config import LoggerMixin, log_dataframe_info, log_processing_step # Добавлен log_processing_step


class SwedbankConverter(SourceConverter, LoggerMixin):
    """
    Converter for Swedbank CSV files to intermediate format.
    """

    def __init__(self, schema_loader: YamlSchemaLoader):
        """
        Initialize Swedbank converter.

        Args:
            schema_loader: Schema loader instance
        """
        self.schema_loader = schema_loader
        self.source_schema = None
        self.target_schema = None
        self.mapping_rules = None

        self._load_schemas_and_mappings()

    def _load_schemas_and_mappings(self) -> None:
        """Load required schemas and mapping rules."""
        try:
            self.source_schema = self.schema_loader.load_schema('swedbank_source.yaml')
            self.target_schema = self.schema_loader.load_schema('intermediate.yaml')
            self.mapping_rules = self.schema_loader.load_mapping('swedbank_to_intermediate.yaml')

            self.logger.info("Loaded Swedbank schemas and mappings")

        except Exception as e:
            self.logger.error(f"Failed to load schemas and mappings for SwedbankConverter: {e}")
            raise

    def load_source_data(self, file_path: str) -> pd.DataFrame:
        """
        Load data from Swedbank CSV file based on its schema.

        Args:
            file_path: Path to the source CSV file

        Returns:
            DataFrame with loaded source data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        file_details = self.source_schema.get('file_details', {})
        delimiter = file_details.get('delimiter', ';')
        encoding = file_details.get('encoding', 'utf-8')

        try:
            df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, keep_default_na=False)
            self.logger.info(f"Loaded {len(df)} rows from {file_path}")
            return df
        except Exception as e:
            self.logger.error(f"Failed to load CSV from {file_path}: {e}")
            raise ValueError(f"Invalid CSV file format or encoding: {e}")

    def validate_source_schema(self, df: pd.DataFrame) -> bool:
        """
        Validate that the source data matches expected schema.

        Args:
            df: DataFrame to validate

        Returns:
            True if schema is valid, False otherwise
        """
        required_fields = {field['name'] for field in self.source_schema.get('fields', []) if field.get('required', False)}
        missing_fields = [field for field in required_fields if field not in df.columns]

        if missing_fields:
            self.logger.error(f"Missing required fields in source data: {', '.join(missing_fields)}")
            return False

        self.logger.info("Source schema validation passed.")
        return True

    def filter_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply row filters based on mapping rules.

        Args:
            df: Input DataFrame

        Returns:
            Filtered DataFrame
        """
        filters = self.mapping_rules.get('filters', [])
        self.logger.debug(f"DEBUG: Filters loaded for SwedbankConverter: {filters}")
        if not filters:
            self.logger.info("No filters defined in mapping rules. Skipping row filtering.")
            return df.copy()
        filtered_df = df.copy()
        initial_count = len(df)

        for f in filters:
            field = f.get('field')
            operator = f.get('operator')
            value = f.get('value')

            if field not in filtered_df.columns:
                self.logger.warning(f"Filter field '{field}' not found in DataFrame. Skipping filter.")
                continue

            if operator == 'equals':
                self.logger.debug(f"DEBUG: Converting column '{field}' to string for comparison with value '{value}'.")
                filtered_df = filtered_df[filtered_df[field].astype(str) == value]
            elif operator == 'not_equals':
                filtered_df = filtered_df[filtered_df[field] != value]
            else:
                self.logger.warning(f"Unsupported filter operator: {operator}")

        log_processing_step(self.logger, "Row Filtering", initial_count, len(filtered_df))
        return filtered_df

    def transform_to_intermediate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform source data to intermediate format.

        Args:
            df: Source DataFrame

        Returns:
            DataFrame in intermediate format
        """
        transformed_data = {}
        field_mappings = self.mapping_rules.get('field_mappings', [])
        intermediate_columns = [field['name'] for field in self.target_schema.get('fields', [])]
        initial_count = len(df)


        for mapping in field_mappings:
            source_field = mapping.get('source_field')
            target_field = mapping.get('target_field')
            transformation = mapping.get('transformation')

            if source_field not in df.columns:
                self.logger.warning(f"Source field '{source_field}' not found in source DataFrame for mapping to '{target_field}'. Skipping transformation for this field.")
                transformed_data[target_field] = pd.Series(dtype='object')
                continue
            else:
                transformed_series = self._apply_transformation(
                    df[source_field],
                    transformation,
                    df # Pass the full DataFrame for transformations that need other columns
                )
            transformed_data[target_field] = transformed_series

        result_df = pd.DataFrame(transformed_data)

        # Ensure all intermediate columns exist, even if not mapped, and order them
        for col in intermediate_columns:
            if col not in result_df.columns:
                result_df[col] = pd.Series(dtype='object', index=result_df.index)

        result_df = result_df[intermediate_columns]

        log_processing_step(self.logger, "Data Transformation to Intermediate", initial_count, len(result_df))
        log_dataframe_info(self.logger, result_df, "Intermediate Data")
        return result_df

    def _apply_transformation(self, series: pd.Series, transformation: Dict[str, Any], full_df: pd.DataFrame) -> pd.Series:
        """
        Apply a single transformation rule to a pandas Series.

        Args:
            series: The pandas Series to transform.
            transformation: Dictionary defining the transformation rule.
            full_df: The complete DataFrame (used for transformations needing other columns, like apply_sign_based_on_field).

        Returns:
            The transformed pandas Series.
        """
        transform_type = transformation.get('type')

        try:
            if transform_type == 'direct_copy':
                return series.copy()

            elif transform_type == 'string_clean':
                remove_apostrophe = False
                for rule in transformation.get('rules', []):
                    if rule.get('action') == 'remove_leading_apostrophe':
                        remove_apostrophe = True
                return series.apply(lambda x: clean_string(str(x) if pd.notna(x) else '', remove_leading_apostrophe=remove_apostrophe))

            elif transform_type == 'anonymize_iban':
                rules = transformation.get('rules', [])
                country_length = 2
                keep_last_digits = 5
                mask_char = "*"
                mask_count = 3
                for rule in rules:
                    if rule.get('action') == 'keep_country_prefix':
                        country_length = rule.get('length', country_length)
                    elif rule.get('action') == 'keep_last_n_digits':
                        keep_last_digits = rule.get('n', keep_last_digits)
                    elif rule.get('action') == 'replace_middle_with':
                        mask_char = rule.get('character', mask_char)
                        mask_count = rule.get('count', mask_count)

                return series.apply(
                    lambda x: anonymize_iban(str(x) if pd.notna(x) else '', country_length, keep_last_digits, mask_char, mask_count)
                )

            elif transform_type == 'calculated_float':
                result_series = series.copy()
                for rule in transformation.get('rules', []):
                    action = rule.get('action')
                    if action == 'replace_decimal_separator':
                        from_sep = rule.get('from', ',')
                        to_sep = rule.get('to', '.')
                        result_series = result_series.apply(lambda x: convert_decimal_separator(str(x) if pd.notna(x) else '', from_sep, to_sep))
                        result_series = result_series.apply(parse_amount) # Parse to float after separator replacement
                    elif action == 'apply_sign_based_on_field':
                        field_for_sign = rule.get('field_for_sign')
                        debit_value = rule.get('debit_value', 'D')
                        credit_value = rule.get('credit_value', 'K')
                        if field_for_sign in full_df.columns:
                            result_series = result_series.combine(full_df[field_for_sign],
                                lambda amount, sign_indicator: apply_amount_sign(amount, sign_indicator, debit_value, credit_value)
                            )
                        else:
                            self.logger.warning(f"Field '{field_for_sign}' for sign application not found. Amounts will not be signed.")
                return result_series

            elif transform_type == 'prefix_string': # Добавлена новая трансформация
                prefix = transformation.get('prefix', '')
                return series.apply(lambda x: prefix_string(str(x) if pd.notna(x) else '', prefix))


            else:
                self.logger.warning(f"Unknown transformation type: {transform_type}")
                return series.copy()

        except Exception as e:
            self.logger.error(f"Transformation failed for type '{transform_type}': {e}")
            return series.copy()

    def get_bank_type(self) -> str: # Добавлен недостающий абстрактный метод
        """
        Return the bank type this converter handles.
        """
        return "swedbank"

    def process_file(self, file_path: str) -> pd.DataFrame:
        """
        Process complete file from source to intermediate format.

        Args:
            file_path: Path to source CSV file

        Returns:
            Processed DataFrame in intermediate format
        """
        self.logger.info(f"Starting processing of file: {file_path}")

        try:
            # Load source data
            df = self.load_source_data(file_path)

            # Validate schema
            if not self.validate_source_schema(df):
                raise ValueError("Source schema validation failed")

            # Filter rows
            filtered_df = self.filter_rows(df)

            if len(filtered_df) == 0:
                self.logger.warning("No rows remaining after filtering")
                return pd.DataFrame()

            # Transform to intermediate format
            result_df = self.transform_to_intermediate(filtered_df)

            self.logger.info(f"Successfully processed file: {file_path}")
            return result_df

        except Exception as e:
            self.logger.error(f"Failed to process file {file_path}: {e}")
            raise