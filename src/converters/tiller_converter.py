# src/converters/tiller_converter.py
"""
Intermediate format to Tiller format converter with Transaction ID-based deduplication.
"""

import csv
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

import pandas as pd
import yaml

from core.interfaces import TargetConverter
from core.schema_loader import YamlSchemaLoader
from utils.date_utils import (
    convert_date_format, date_to_month_start, date_to_week_start, get_current_date
)
from utils.google_sheets_reader import create_sheets_reader
from utils.logging_config import LoggerMixin, log_dataframe_info
from utils.string_utils import prefix_string, normalize_tiller_transaction_id


class TillerConverter(TargetConverter, LoggerMixin):
    """
    Converter from intermediate format to Tiller format with Transaction ID-based deduplication.
    """

    def __init__(self, schema_loader: YamlSchemaLoader, tiller_config: Optional[Dict[str, Any]] = None,
                 accounts_file: Optional[str] = None):
        """
        Initialize Tiller converter.

        Args:
            schema_loader: Schema loader instance
            tiller_config: Tiller history source configuration for deduplication
            accounts_file: Path to accounts configuration file (optional)
        """
        self.schema_loader = schema_loader
        self.source_schema = None  # Intermediate schema is source for Tiller
        self.target_schema = None  # Tiller target schema
        self.mapping_rules = None
        self.accounts_config = None
        self.accounts_file = accounts_file or "config/tiller/accounts.yaml"
        self._loaded_accounts_configs: Dict[str, Dict[str, Any]] = {}

        # Deduplication components
        self.tiller_config = tiller_config or {}
        self.sheets_reader = None
        self.exclusion_set: Set[str] = set()  # Set of existing Transaction IDs
        self.deduplication_enabled = False

        self._load_schemas_and_mappings()
        self._load_accounts_config()
        self._initialize_deduplication()

    def _load_schemas_and_mappings(self) -> None:
        """Load required schemas and mapping rules."""
        try:
            self.source_schema = self.schema_loader.load_schema('intermediate.yaml')
            self.target_schema = self.schema_loader.load_schema('tiller_target.yaml')
            self.mapping_rules = self.schema_loader.load_mapping('intermediate_to_tiller.yaml')

            self.logger.info("Loaded Tiller schemas and mappings")

        except Exception as e:
            self.logger.error(f"Failed to load schemas and mappings for TillerConverter: {e}")
            raise

    def _load_accounts_config(self) -> None:
        """Load accounts mapping configuration."""
        try:
            config_path = Path(self.accounts_file)
            if not config_path.exists():
                self.logger.warning(
                    f"Accounts configuration file not found at {config_path}. Account enrichment will be skipped.")
                self.accounts_config = {'accounts': []}
                return

            # Direct yaml.safe_load: accounts.yaml is not a schema/mapping file,
            # so schema_loader (which resolves schema/mapping paths) is not appropriate here.
            with open(config_path, 'r', encoding='utf-8') as file:
                self.accounts_config = yaml.safe_load(file)
            self.logger.info(f"Loaded accounts configuration from {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load accounts configuration: {e}")
            self.accounts_config = {'accounts': []}

    def _initialize_deduplication(self) -> None:
        """Initialize deduplication functionality."""
        try:
            if not self.tiller_config.get('enabled', False):
                self.logger.info("Tiller deduplication disabled in configuration")
                return

            # Initialize Google Sheets reader
            self.sheets_reader = create_sheets_reader(self.tiller_config)
            if self.sheets_reader is None:
                self.logger.warning("Failed to initialize Google Sheets reader. Deduplication disabled.")
                return

            # Load existing Transaction IDs
            self._load_exclusion_set()
            self.deduplication_enabled = True
            self.logger.info("Tiller deduplication initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize deduplication: {e}")
            self.logger.warning("Proceeding without deduplication")
            self.deduplication_enabled = False

    def _load_exclusion_set(self) -> None:
        """Load existing Transaction IDs from Tiller sheet into exclusion set."""
        try:
            spreadsheet_id = self.tiller_config.get('spreadsheet_id')
            worksheet_title = self.tiller_config.get('worksheet_title')
            table_name = self.tiller_config.get('table_name')

            if not spreadsheet_id or not worksheet_title:
                raise ValueError("Missing spreadsheet_id or worksheet_title in tiller_history_source configuration")

            self.logger.info("Loading existing Transaction IDs from Tiller sheet...")

            # Load Transaction IDs from Google Sheets
            raw_ids: Set[str] = self.sheets_reader.load_transaction_ids(
                spreadsheet_id=spreadsheet_id,
                worksheet_title=worksheet_title,
                table_name=table_name
            )

            # Normalize transaction IDs
            self.exclusion_set = {
                normalize_tiller_transaction_id(tid)
                for tid in raw_ids
                if normalize_tiller_transaction_id(tid)
            }

            self.logger.info(f"Loaded {len(self.exclusion_set)} existing Transaction IDs for deduplication")

        except Exception as e:
            self.logger.error(f"Failed to load exclusion set: {e}")
            raise

    def get_target_type(self) -> str:
        """
        Return the target system type this converter handles.

        Returns:
            Target system identifier
        """
        return "tiller"

    def load_intermediate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Load (or rather, receive) intermediate data.
        For TillerConverter, intermediate data is the input, so we just return it.

        Args:
            df: Intermediate DataFrame

        Returns:
            DataFrame (same as input for this converter)
        """
        self.logger.info("Intermediate data received for Tiller transformation.")
        log_dataframe_info(self.logger, df, "Intermediate DataFrame before Tiller validation")
        return df

    def validate_intermediate_schema(self, df: pd.DataFrame) -> bool:
        """
        Validate that the intermediate data matches the expected intermediate schema.
        This ensures the data received is in the correct format for Tiller transformation.

        Args:
            df: Intermediate DataFrame to validate

        Returns:
            True if schema is valid, False otherwise
        """
        if self.source_schema is None:
            self.logger.error("Source schema (intermediate.yaml) not loaded for validation.")
            return False

        # Get expected fields and their types from the intermediate schema
        expected_fields = {field['name']: field.get('type') for field in self.source_schema.get('fields', [])}

        # Check for missing columns
        missing_columns = [col for col in expected_fields if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Intermediate schema validation failed: Missing columns: {', '.join(missing_columns)}")
            return False

        self.logger.info("Intermediate schema validation successful.")
        return True

    def _apply_deduplication(self, df: pd.DataFrame, transaction_id_column: str = 'Transaction ID') -> pd.DataFrame:
        """
        Apply deduplication logic to remove transactions already in Tiller.
        Uses Transaction ID for matching.

        Args:
            df: Input DataFrame with new transactions (in Tiller format)
            transaction_id_column: Name of the Transaction ID column

        Returns:
            DataFrame with duplicates removed
        """
        if not self.deduplication_enabled or len(self.exclusion_set) == 0:
            self.logger.info("Deduplication skipped (disabled or no historical data)")
            return df

        if transaction_id_column not in df.columns:
            self.logger.error(
                f"Transaction ID column '{transaction_id_column}' not found in DataFrame. Skipping deduplication.")
            return df

        self.logger.info(f"Starting deduplication against {len(self.exclusion_set)} existing Transaction IDs")

        # Track duplicates for reporting
        duplicates_found = []
        original_count = len(df)

        # Check each transaction ID against the exclusion set
        def is_duplicate(row):
            transaction_id = str(row[transaction_id_column]).strip()
            if transaction_id in self.exclusion_set:
                duplicates_found.append({
                    'transaction_id': transaction_id,
                    'date': row.get('Date', ''),
                    'amount': row.get('Amount', ''),
                    'description': row.get('Description', '')[:50]
                })
                return False  # Exclude this row
            return True  # Keep this row

        # Filter out duplicates
        filtered_df = df[df.apply(is_duplicate, axis=1)].copy()

        # Log results
        filtered_count = len(filtered_df)
        removed_count = original_count - filtered_count

        self.logger.info(
            f"Deduplication completed: {removed_count} duplicates removed, {filtered_count} transactions remaining")

        if duplicates_found:
            self.logger.info("Duplicate transactions found:")
            for dup in duplicates_found[:5]:  # Log first 5 duplicates
                self.logger.info(
                    f"  - ID: {dup['transaction_id']} | {dup['date']} | {dup['amount']} | {dup['description']}...")
            if len(duplicates_found) > 5:
                self.logger.info(f"  ... and {len(duplicates_found) - 5} more duplicates")

        return filtered_df

    def transform_to_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform intermediate data to Tiller format with Transaction ID-based deduplication.

        Args:
            df: Intermediate DataFrame

        Returns:
            DataFrame in target format with duplicates removed
        """
        self.logger.info("Starting transformation to Tiller format...")
        log_dataframe_info(self.logger, df, "Intermediate DataFrame before Tiller transformation")

        if len(df) == 0:
            self.logger.info("No transactions to transform")
            return pd.DataFrame()

        output_df = pd.DataFrame()
        target_fields = self.target_schema.get('fields', [])
        target_field_names = [field.get('name') for field in target_fields if field.get('name')]

        for mapping in self.mapping_rules.get('field_mappings', []):
            source_field = mapping.get('source_field')
            target_field = mapping.get('target_field')
            transformation = mapping.get('transformation', {})
            transform_type = transformation.get('type')

            if target_field not in target_field_names:
                self.logger.warning(f"Target field '{target_field}' from mapping not found in Tiller schema. Skipping.")
                continue

            # Ensure the target column exists in the output DataFrame
            if target_field not in output_df.columns:
                target_field_type = next((f.get('type') for f in target_fields if f.get('name') == target_field),
                                         'string')
                output_df[target_field] = '' if target_field_type == 'string' else None

            if transform_type == 'direct_copy':
                if source_field and source_field in df.columns:
                    output_df[target_field] = df[source_field]
                else:
                    self.logger.warning(
                        f"Source field '{source_field}' not found for direct_copy to '{target_field}'. Setting to default.")
            elif transform_type == 'date_format_conversion':
                if source_field and source_field in df.columns:
                    source_format = transformation.get('source_format')
                    target_format = transformation.get('target_format')
                    output_df[target_field] = df[source_field].apply(
                        lambda x: convert_date_format(str(x), source_format, target_format) if pd.notna(x) else ''
                    )
                else:
                    self.logger.warning(
                        f"Source field '{source_field}' not found for date_format_conversion to '{target_field}'. Setting to default.")
            elif transform_type == 'date_to_month_start':
                if source_field and source_field in df.columns:
                    source_format = transformation.get('source_format')
                    target_format = transformation.get('target_format')
                    output_df[target_field] = df[source_field].apply(
                        lambda x: date_to_month_start(str(x), source_format, target_format) if pd.notna(x) else ''
                    )
                else:
                    self.logger.warning(
                        f"Source field '{source_field}' not found for date_to_month_start to '{target_field}'. Setting to default.")
            elif transform_type == 'date_to_week_start':
                if source_field and source_field in df.columns:
                    source_format = transformation.get('source_format')
                    target_format = transformation.get('target_format')
                    start_of_week = transformation.get('start_of_week', 'Sunday')
                    output_df[target_field] = df[source_field].apply(
                        lambda x: date_to_week_start(str(x), source_format, target_format, start_of_week) if pd.notna(
                            x) else ''
                    )
                else:
                    self.logger.warning(
                        f"Source field '{source_field}' not found for date_to_week_start to '{target_field}'. Setting to default.")
            elif transform_type == 'current_date':
                target_format = transformation.get('target_format')
                output_df[target_field] = get_current_date(target_format)
            elif transform_type == 'prefix_string':
                if source_field and source_field in df.columns:
                    prefix = transformation.get('prefix', '')
                    output_df[target_field] = df[source_field].apply(
                        lambda x: prefix_string(str(x), prefix) if pd.notna(x) else ''
                    )
                else:
                    self.logger.warning(
                        f"Source field '{source_field}' not found for prefix_string to '{target_field}'. Setting to default.")
            elif transform_type in ['lookup_account_name', 'lookup_account_id', 'lookup_bank_name']:
                if source_field and source_field in df.columns:
                    accounts_config_file = transformation.get('accounts_config_file')
                    lookup_key_field = transformation.get('lookup_key_field')

                    if not lookup_key_field:
                        self.logger.error(
                            f"Missing 'lookup_key_field' in transformation rule for '{transform_type}'. Cannot perform lookup.")
                        output_df[target_field] = ''
                        continue

                    accounts_data = self._get_accounts_data_for_lookup(accounts_config_file)

                    # Determine which field to extract from the account data based on transformation type
                    target_field_in_account_data = None
                    if transform_type == 'lookup_account_name':
                        target_field_in_account_data = 'account_name'
                    elif transform_type == 'lookup_account_id':
                        target_field_in_account_data = 'tiller_account_id'
                    elif transform_type == 'lookup_bank_name':
                        target_field_in_account_data = 'bank'

                    if not target_field_in_account_data:
                        self.logger.error(
                            f"Invalid target field configuration for transformation type: {transform_type}")
                        output_df[target_field] = ''
                        continue

                    # Create the mapping dictionary
                    lookup_map = {acc.get(lookup_key_field): acc.get(target_field_in_account_data)
                                  for acc in accounts_data if lookup_key_field in acc}

                    output_df[target_field] = df[source_field].map(lookup_map).fillna('')
                else:
                    self.logger.warning(
                        f"Source field '{source_field}' not found for {transform_type} to '{target_field}'. Setting to default.")
                    output_df[target_field] = ''

            else:
                self.logger.warning(
                    f"Unsupported or missing transformation type '{transform_type}' for target field '{target_field}'. Setting to default.")

        # Ensure all target schema fields are present, even if not explicitly mapped
        for field in target_field_names:
            if field not in output_df.columns:
                target_field_type = next((f.get('type') for f in target_fields if f.get('name') == field), 'string')
                output_df[field] = '' if target_field_type == 'string' else None

        # Also ensure that any None values in string columns become empty strings for CSV output
        for col in output_df.columns:
            if output_df[col].dtype == 'object':
                output_df[col] = output_df[col].fillna('')

        # Reorder columns to match the target schema
        output_df = output_df[target_field_names]

        self.logger.info("Transformation to Tiller format completed.")
        log_dataframe_info(self.logger, output_df, "Tiller DataFrame after transformation")

        # Apply deduplication AFTER transformation (when Transaction ID is available)
        output_df = self._apply_deduplication(output_df)

        return output_df

    def _get_accounts_data_for_lookup(self, accounts_config_file: Optional[str]) -> List[Dict[str, Any]]:
        """
        Retrieves account data either from cache, loads it dynamically, or falls back to default.
        """
        if accounts_config_file:
            # Check cache first
            if accounts_config_file in self._loaded_accounts_configs:
                return self._loaded_accounts_configs[accounts_config_file].get('accounts', [])

            # Load dynamically if not in cache
            try:
                self.logger.debug(f"Loading accounts config dynamically from {accounts_config_file}")
                with open(accounts_config_file, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                self._loaded_accounts_configs[accounts_config_file] = loaded_config
                return loaded_config.get('accounts', [])
            except FileNotFoundError:
                self.logger.error(f"Accounts config file not found: '{accounts_config_file}'. Falling back to default.")
                return self.accounts_config.get('accounts', [])
            except Exception as e:
                self.logger.error(
                    f"Error loading dynamic accounts config '{accounts_config_file}': {e}. Falling back to default.")
                return self.accounts_config.get('accounts', [])
        else:
            # If no specific file is mentioned in the mapping rule, use the default loaded at init
            self.logger.debug("No specific accounts_config_file in mapping. Using default accounts config.")
            return self.accounts_config.get('accounts', [])

    def save_to_csv(self, df: pd.DataFrame, file_path: str, output_config: Dict[str, Any]) -> None:
        """
        Saves the DataFrame to a CSV file in Tiller format.
        """
        try:
            # Get CSV details from tiller_target.yaml (loaded into self.target_schema)
            file_details = self.target_schema.get('file_details', {})
            delimiter = file_details.get('delimiter', ',')
            quote_char = file_details.get('quote_char', '"')
            decimal_separator = file_details.get('decimal_separator', '.')
            encoding = output_config.get('encoding', 'utf-8')  # Encoding from the main config

            # Use pandas.to_csv to write the file
            # quoting=csv.QUOTE_ALL ensures that all values are enclosed in quotes
            # This addresses your request for commas not to split cells.
            df.to_csv(
                file_path,
                sep=delimiter,
                index=False,  # Do not write DataFrame index as a separate column
                encoding=encoding,
                quoting=csv.QUOTE_ALL,  # Always enclose values in quotes
                quotechar=quote_char,  # Quoting character
                decimal=decimal_separator  # Decimal separator for numbers
            )
            self.logger.info(f"Tiller data successfully saved to file: '{file_path}'")
        except Exception as e:
            self.logger.error(f"Error saving Tiller data to CSV file '{file_path}': {e}")
            raise  # Re-raise the error to propagate pipeline failure

    def format_for_console(self, df: pd.DataFrame, max_rows: int = 50) -> str:
        """
        Format DataFrame for console display.

        Args:
            df: DataFrame to format
            max_rows: Maximum number of rows to display
        Returns:
            Formatted string representation
        """
        if len(df) == 0:
            return "No data to display"

        display_df = df.head(max_rows)

        output_lines = []
        output_lines.append(f"Tiller Transaction Data ({len(df)} total rows, showing {len(display_df)}):")
        output_lines.append("=" * 80)

        key_columns = ['Date', 'Description', 'Amount', 'Account #', 'From / To', 'Transaction ID']
        available_columns = [col for col in key_columns if col in display_df.columns]

        if available_columns:
            compact_df = display_df[available_columns].copy()

            if 'Description' in compact_df.columns:
                compact_df['Description'] = compact_df['Description'].apply(
                    lambda x: (str(x)[:30] + '...') if len(str(x)) > 30 else str(x)
                )

            output_lines.append(compact_df.to_string(index=False))
        else:
            output_lines.append(display_df.to_string(index=False))

        if len(df) > max_rows:
            output_lines.append(f"... showing only first {max_rows} rows.")
        output_lines.append("=" * 80)
        return "\n".join(output_lines)

    def save_output(self, df: pd.DataFrame, config, target_name: str = 'tiller') -> None:
        """
        Save target format output to file and/or console.

        Args:
            df: DataFrame in target (Tiller) format
            config: ConfigManager instance
            target_name: Name of the target system for headers
        """
        output_config = config.get_output_config()
        tiller_config = output_config.get(f'{target_name}_format', {})

        destination = tiller_config.get('destination', 'both')

        if destination in ['file', 'both']:
            file_path = tiller_config.get('file_path', f'output/{target_name}_transactions.csv')
            self.save_to_csv(df, file_path, output_config)

        if destination in ['console', 'both']:
            console_limit = tiller_config.get('console_limit', 50)
            formatted_output = self.format_for_console(df, console_limit)
            print("\n" + "=" * 80)
            print(f"{target_name.upper()} FORMAT DATA (Ready for copy-paste):")
            print("=" * 80)
            print(formatted_output)
            print("=" * 80)