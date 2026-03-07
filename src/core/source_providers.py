# src/core/source_providers.py
"""
Implementations of SourceProvider for local and Google Drive sources.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from core.interfaces import SourceProvider
from utils.file_utils import get_input_files


class LocalSourceProvider(SourceProvider):
    """
    Provides access to files from a local directory.
    """

    def __init__(self, input_dir: str, supported_extensions: List[str],
                 logger: Optional[logging.Logger] = None):
        self.input_dir = input_dir
        self.supported_extensions = supported_extensions
        self.logger = logger or logging.getLogger(__name__)

    def list_files(self) -> List[Dict[str, Any]]:
        """List files in local directory."""
        try:
            files = get_input_files(self.input_dir, self.supported_extensions, self.logger)
            return [{'name': f.name, 'identifier': f} for f in files]
        except Exception as e:
            self.logger.error(f"Failed to list local files in {self.input_dir}: {e}")
            return []

    def get_file_content(self, identifier: Any) -> io.BytesIO:
        """Read local file into BytesIO buffer."""
        file_path = Path(identifier)
        if not file_path.exists():
            raise FileNotFoundError(f"Local file not found: {file_path}")

        with open(file_path, 'rb') as f:
            return io.BytesIO(f.read())


class GDriveSourceProvider(SourceProvider):
    """
    Provides access to files from a Google Drive folder.
    """

    def __init__(self, folder_id: str, credentials_file: str,
                 supported_extensions: List[str],
                 logger: Optional[logging.Logger] = None):
        self.folder_id = folder_id
        self.credentials_file = credentials_file
        self.supported_extensions = supported_extensions
        self.logger = logger or logging.getLogger(__name__)
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Drive API."""
        try:
            scopes = ['https://www.googleapis.com/auth/drive.readonly']
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file, scopes=scopes)
            self.service = build('drive', 'v3', credentials=creds)
            self.logger.info("Authenticated with Google Drive API successfully")
        except Exception as e:
            self.logger.error(f"Failed to authenticate with Google Drive: {e}")
            raise

    def list_files(self) -> List[Dict[str, Any]]:
        """List CSV files in the GDrive folder."""
        try:
            # Build query for CSV files in specific folder
            query = f"'{self.folder_id}' in parents and trashed = false and mimeType = 'text/csv'"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=100
            ).execute()

            files = results.get('files', [])
            return [{'name': f['name'], 'identifier': f['id']} for f in files]
        except Exception as e:
            self.logger.error(f"Failed to list GDrive files: {e}")
            return []

    def get_file_content(self, identifier: Any) -> io.BytesIO:
        """Download GDrive file into BytesIO buffer."""
        try:
            request = self.service.files().get_media(fileId=identifier)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            buffer.seek(0)
            return buffer
        except Exception as e:
            self.logger.error(f"Failed to download file {identifier} from GDrive: {e}")
            raise


class SourceProviderFactory:
    """
    Factory for creating SourceProvider instances.
    """

    @staticmethod
    def create(config: Any, logger: Optional[logging.Logger] = None) -> SourceProvider:
        source_config = config.get('source', {})
        source_type = source_config.get('type', 'local')
        files_config = config.get('files', {})
        extensions = files_config.get('supported_extensions', ['.csv'])

        if source_type == 'local':
            local_config = source_config.get('local', {})
            return LocalSourceProvider(
                input_dir=local_config.get('input_dir', 'data/input'),
                supported_extensions=extensions,
                logger=logger
            )
        elif source_type == 'gdrive':
            gdrive_config = source_config.get('gdrive', {})
            auth_config = config.get('google_auth', {})
            return GDriveSourceProvider(
                folder_id=gdrive_config.get('input_folder_id'),
                credentials_file=auth_config.get('credentials_file'),
                supported_extensions=extensions,
                logger=logger
            )
        else:
            raise ValueError(f"Unknown source type: {source_type}")
