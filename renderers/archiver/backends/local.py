"""
Local filesystem storage backend for archiver.
"""

import os
import shutil
from datetime import datetime, timezone
from typing import Dict, Any, List

from utils.logging_utils import log_operation
from .base import StorageBackend, logger

class LocalBackend(StorageBackend):
    """Storage backend that saves backups to a local directory."""

    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize the local storage backend.
        
        Args:
            settings: Must contain:
                - path: Absolute path to backup directory
        """
        super().__init__(settings)
        
        if 'path' not in settings:
            raise ValueError("Local backend requires 'path' setting")
        
        # Create backup directory if it doesn't exist
        os.makedirs(settings['path'], exist_ok=True)
        
        logger.logger.info("Initialized local storage backend",
                        backup_path=settings['path'])
    
    @log_operation(logger.logger)
    def upload(self, local_file_path: str, remote_filename: str) -> bool:
        """Upload a backup file by copying it to the backup directory.
        
        Args:
            local_file_path: Path to the local file to copy
            remote_filename: Name to give the file in the backup directory
            
        Returns:
            bool: True if copy was successful, False otherwise
        """
        try:
            dest_path = os.path.join(self.settings['path'], remote_filename)
            shutil.copy2(local_file_path, dest_path)
            
            file_size = os.path.getsize(dest_path)
            logger.logger.info("Backup file copied successfully",
                           source=local_file_path,
                           destination=dest_path,
                           size_bytes=file_size)
            return True
            
        except Exception as e:
            logger.logger.error("Failed to copy backup file",
                            error=str(e),
                            error_type=type(e).__name__,
                            source=local_file_path,
                            destination=self.settings['path'])
            return False
    
    @log_operation(logger.logger)
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all backups in the backup directory.
        
        Returns:
            List of dictionaries containing backup information
        """
        backups = []
        try:
            for filename in os.listdir(self.settings['path']):
                if not filename.endswith('.bundle'):
                    continue
                
                filepath = os.path.join(self.settings['path'], filename)
                timestamp = self._parse_backup_timestamp(filename)
                if timestamp:
                    backups.append({
                        'filename': filename,
                        'timestamp': timestamp,
                        'size': os.path.getsize(filepath)
                    })
            
            logger.logger.info("Listed local backups",
                           backup_count=len(backups))
            return backups
            
        except Exception as e:
            logger.logger.error("Failed to list backups",
                            error=str(e),
                            error_type=type(e).__name__,
                            path=self.settings['path'])
            return []
    
    @log_operation(logger.logger)
    def cleanup(self, retention_days: int) -> None:
        """Remove backup files older than retention_days.
        
        Args:
            retention_days: Number of days to keep backups for
        """
        try:
            now = datetime.now(timezone.utc)
            removed = 0
            
            for backup in self.list_backups():
                age = now - backup['timestamp'].replace(tzinfo=timezone.utc)
                if age.days > retention_days:
                    filepath = os.path.join(self.settings['path'], backup['filename'])
                    os.remove(filepath)
                    removed += 1
            
            logger.logger.info("Cleanup completed",
                           removed_count=removed,
                           retention_days=retention_days)
                    
        except Exception as e:
            logger.logger.error("Failed to cleanup old backups",
                            error=str(e),
                            error_type=type(e).__name__,
                            path=self.settings['path'])