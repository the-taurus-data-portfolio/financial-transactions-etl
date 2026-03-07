# src/core/archivers.py
"""
Implementations of SourceArchiver for local and Google Drive destinations.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from core.interfaces import SourceArchiver
from utils.file_utils import LocalFileArchiver


class GDriveFileArchiver(SourceArchiver):
    """
    Archives processed files by moving them to another folder on Google Drive.
    """

    def __init__(self, archive_folder_id: str, input_folder_id: str,
                 credentials_file: str, logger: Optional[logging.Logger] = None):
        self.archive_folder_id = archive_folder_id
        self.input_folder_id = input_folder_id
        self.credentials_file = credentials_file
        self.logger = logger or logging.getLogger(__name__)
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Drive API."""
        try:
            scopes = ['https://www.googleapis.com/auth/drive']
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file, scopes=scopes)
            self.service = build('drive', 'v3', credentials=creds)
            self.logger.info("Authenticated with Google Drive API for archiving successfully")
        except Exception as e:
            self.logger.error(f"Failed to authenticate with Google Drive for archiving: {e}")
            raise

    def archive(self, file_identifiers: List[Any]) -> bool:
        """
        Move GDrive files from input folder to archive folder.

        Args:
            file_identifiers: List of GDrive file IDs

        Returns:
            True if all files were successfully archived, False otherwise
        """
        if not file_identifiers:
            self.logger.info("No GDrive files to archive")
            return True

        success_count = 0
        for file_id in file_identifiers:
            try:
                # Get file metadata to confirm name and current parents
                file = self.service.files().get(fileId=file_id, fields='name, parents').execute()
                file_name = file.get('name')
                previous_parents = ",".join(file.get('parents', []))

                # Update file to change parents
                self.service.files().update(
                    fileId=file_id,
                    addParents=self.archive_folder_id,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()

                self.logger.info(f"Archived GDrive file: {file_name} ({file_id})")
                success_count += 1
            except Exception as e:
                self.logger.error(f"Failed to archive GDrive file {file_id}: {e}")

        return success_count == len(file_identifiers)


class ArchiverFactory:
    """
    Factory for creating SourceArchiver instances.
    """

    @staticmethod
    def create(config: Any, logger: Optional[logging.Logger] = None) -> Optional[SourceArchiver]:
        archiving_config = config.get('archiving', {})
        if not archiving_config.get('enabled', False):
            return None

        archiver_type = archiving_config.get('type', 'local')

        if archiver_type == 'local':
            local_config = archiving_config.get('local', {})
            return LocalFileArchiver(
                archive_dir=local_config.get('archive_dir', 'data/archive'),
                add_timestamp=local_config.get('add_timestamp', False),
                logger=logger
            )
        elif archiver_type == 'gdrive':
            gdrive_config = archiving_config.get('gdrive', {})
            source_config = config.get('source', {}).get('gdrive', {})
            auth_config = config.get('google_auth', {})

            return GDriveFileArchiver(
                archive_folder_id=gdrive_config.get('archive_folder_id'),
                input_folder_id=source_config.get('input_folder_id'),
                credentials_file=auth_config.get('credentials_file'),
                logger=logger
            )
        else:
            raise ValueError(f"Unknown archiver type: {archiver_type}")
