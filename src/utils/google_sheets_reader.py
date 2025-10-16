# src/utils/google_sheets_reader.py
"""
Google Sheets reader utility for accessing Tiller transaction IDs.
Simplified version focusing on Transaction ID column retrieval only.
"""

import logging
from pathlib import Path
from typing import Set, Dict, Any, Optional
import gspread
from google.oauth2.service_account import Credentials

from src.utils.logging_config import LoggerMixin


class GoogleSheetsReader(LoggerMixin):
    """
    Helper class for secure Google Sheets API connection and Transaction ID retrieval.
    """

    def __init__(self, credentials_file: str):
        """
        Initialize Google Sheets reader with service account credentials.

        Args:
            credentials_file: Path to Google service account JSON file
        """
        self.credentials_file = credentials_file
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Google Sheets client with proper authentication."""
        try:
            credentials_path = Path(self.credentials_file)

            if not credentials_path.exists():
                raise FileNotFoundError(f"Google credentials file not found: {self.credentials_file}")

            # Define the scope for Google Sheets API
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]

            # Authenticate using service account credentials
            credentials = Credentials.from_service_account_file(
                str(credentials_path),
                scopes=scope
            )

            # Initialize gspread client
            self.client = gspread.authorize(credentials)
            self.logger.info("Google Sheets client initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Google Sheets client: {e}")
            raise

    def load_transaction_ids(self, spreadsheet_id: str, worksheet_title: str,
                             table_name: Optional[str] = None) -> Set[str]:
        """
        Load Transaction IDs from specified Google Sheet table/worksheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            worksheet_title: Title of the worksheet (e.g., 'Transactions')
            table_name: Optional name of the table within the sheet (e.g., 'Table1')

        Returns:
            Set of Transaction IDs for efficient lookup

        Raises:
            Exception: If sheet access fails or Transaction ID column not found
        """
        try:
            self.logger.info(f"Loading Transaction IDs from spreadsheet {spreadsheet_id}, "
                             f"worksheet: {worksheet_title}")

            # Open the spreadsheet
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Get the specified worksheet by title
            worksheet = spreadsheet.worksheet(worksheet_title)

            # Get all data as records (list of dictionaries)
            # This automatically uses the first row as headers
            all_records = worksheet.get_all_records()

            if not all_records:
                self.logger.warning(f"No data found in worksheet '{worksheet_title}'")
                return set()

            # Extract Transaction ID column
            transaction_ids = set()
            transaction_id_column = 'Transaction ID'  # Expected column name in Tiller

            for record in all_records:
                if transaction_id_column in record:
                    tid = record[transaction_id_column]
                    if tid and str(tid).strip():  # Only add non-empty IDs
                        transaction_ids.add(str(tid).strip())
                else:
                    # If first record doesn't have the column, raise error
                    if not transaction_ids:
                        raise ValueError(
                            f"Column '{transaction_id_column}' not found in worksheet '{worksheet_title}'. "
                            f"Available columns: {list(record.keys())}")

            self.logger.info(f"Successfully loaded {len(transaction_ids)} Transaction IDs from Google Sheets")
            return transaction_ids

        except gspread.SpreadsheetNotFound:
            raise Exception(f"Spreadsheet not found: {spreadsheet_id}")
        except gspread.WorksheetNotFound:
            raise Exception(f"Worksheet not found: {worksheet_title}")
        except Exception as e:
            self.logger.error(f"Failed to load Transaction IDs: {e}")
            raise

    def validate_sheet_access(self, spreadsheet_id: str, worksheet_title: str) -> bool:
        """
        Validate that the specified sheet and worksheet are accessible.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            worksheet_title: Worksheet title

        Returns:
            True if accessible, False otherwise
        """
        try:
            # Try to open the spreadsheet
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            # Check if worksheet exists
            worksheet = spreadsheet.worksheet(worksheet_title)

            self.logger.info(f"Sheet access validated for {spreadsheet_id}:{worksheet_title}")
            return True

        except Exception as e:
            self.logger.error(f"Sheet access validation failed: {e}")
            return False

    def get_sheet_info(self, spreadsheet_id: str, worksheet_title: str) -> Dict[str, Any]:
        """
        Get information about the specified sheet.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            worksheet_title: Worksheet title

        Returns:
            Dictionary containing sheet information
        """
        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(worksheet_title)

            info = {
                'title': spreadsheet.title,
                'worksheet_title': worksheet.title,
                'row_count': worksheet.row_count,
                'col_count': worksheet.col_count,
                'url': spreadsheet.url
            }

            return info

        except Exception as e:
            self.logger.error(f"Failed to get sheet info: {e}")
            return {}


def create_sheets_reader(config: Dict[str, Any]) -> Optional[GoogleSheetsReader]:
    """
    Factory function to create GoogleSheetsReader from configuration.

    Args:
        config: Configuration dictionary containing credentials_file

    Returns:
        GoogleSheetsReader instance or None if disabled/failed
    """
    logger = logging.getLogger(__name__)

    try:
        if not config.get('enabled', False):
            logger.info("Google Sheets integration disabled in configuration")
            return None

        credentials_file = config.get('credentials_file')
        if not credentials_file:
            logger.error("No credentials_file specified in tiller_history_source configuration")
            return None

        reader = GoogleSheetsReader(credentials_file)
        logger.info("Google Sheets reader created successfully")
        return reader

    except Exception as e:
        logger.error(f"Failed to create Google Sheets reader: {e}")
        return None