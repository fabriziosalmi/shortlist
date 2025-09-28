"""
Abstract base class for archiver storage backends.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import os
from typing import Dict, Any, List, Optional

from utils.logging_config import configure_logging
from utils.logging_utils import ComponentLogger, RENDERER_CONTEXT, log_operation

# Configure logging
logger = ComponentLogger('archiver_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='archiver')

class StorageBackend(ABC):
    """Abstract base class for backup storage backends."""

    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize the storage backend.
        
        Args:
            settings: Backend-specific configuration settings
        """
        self.settings = settings
    
    @abstractmethod
    def upload(self, local_file_path: str, remote_filename: str) -> bool:
        """Upload a backup file to the storage backend.
        
        Args:
            local_file_path: Path to the local file to upload
            remote_filename: Name to give the file in the remote storage
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all backups in the storage backend.
        
        Returns:
            List of dictionaries containing backup information:
            - filename: Name of the backup file
            - timestamp: Creation timestamp
            - size: Size in bytes
        """
        pass
    
    @abstractmethod
    def cleanup(self, retention_days: int) -> None:
        """Remove backups older than the retention period.
        
        Args:
            retention_days: Number of days to keep backups for
        """
        pass
    
    def _parse_backup_timestamp(self, filename: str) -> Optional[datetime]:
        """Extract timestamp from a backup filename.
        
        Args:
            filename: Backup filename (format: shortlist-backup-YYYYMMDDTHHmmssZ.bundle)
            
        Returns:
            datetime object if timestamp was parsed successfully, None otherwise
        """
        try:
            # Extract timestamp part: shortlist-backup-20250929T030000Z.bundle -> 20250929T030000Z
            timestamp_str = filename.split('-')[2].split('.')[0]
            return datetime.strptime(timestamp_str, "%Y%m%dT%H%M%SZ")
        except (IndexError, ValueError):
            logger.logger.warning("Failed to parse backup timestamp",
                              filename=filename)
            return None