"""
SFTP storage backend for archiver.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pysftp
import stat

from utils.logging_utils import log_operation
from .base import StorageBackend, logger

class SFTPBackend(StorageBackend):
    """Storage backend that saves backups to a remote SFTP server."""

    def __init__(self, settings: Dict[str, Any]) -> None:
        """Initialize the SFTP storage backend.
        
        Args:
            settings: Must contain:
                - host: SFTP server hostname
                - port: SFTP server port (default: 22)
                - username: SFTP username
                - remote_path: Absolute path on remote server
        
        The following authentication methods are supported through environment variables:
        - SFTP_PASSWORD: Password authentication
        - SFTP_PRIVATE_KEY_PATH: Path to SSH private key file
        """
        super().__init__(settings)
        
        required_settings = ['host', 'username', 'remote_path']
        missing = [s for s in required_settings if s not in settings]
        if missing:
            raise ValueError(f"SFTP backend requires settings: {', '.join(missing)}")
        
        # Set default port if not specified
        if 'port' not in settings:
            settings['port'] = 22
            
        # Verify authentication method
        self.password = os.getenv('SFTP_PASSWORD')
        self.private_key_path = os.getenv('SFTP_PRIVATE_KEY_PATH')
        if not self.password and not self.private_key_path:
            raise ValueError("No authentication method available. Set SFTP_PASSWORD or SFTP_PRIVATE_KEY_PATH")
        
        # Configure SFTP connection settings
        self.cnopts = pysftp.CnOpts()
        self.cnopts.hostkeys = None  # Disable host key checking
        
        logger.logger.info("Initialized SFTP storage backend",
                        host=settings['host'],
                        port=settings['port'],
                        username=settings['username'],
                        remote_path=settings['remote_path'],
                        auth_type="password" if self.password else "key")
    
    def _connect(self) -> pysftp.Connection:
        """Create an SFTP connection using configured authentication."""
        try:
            if self.password:
                return pysftp.Connection(
                    host=self.settings['host'],
                    port=self.settings['port'],
                    username=self.settings['username'],
                    password=self.password,
                    cnopts=self.cnopts
                )
            else:
                return pysftp.Connection(
                    host=self.settings['host'],
                    port=self.settings['port'],
                    username=self.settings['username'],
                    private_key=self.private_key_path,
                    cnopts=self.cnopts
                )
        except Exception as e:
            logger.logger.error("Failed to connect to SFTP server",
                            error=str(e),
                            error_type=type(e).__name__,
                            host=self.settings['host'],
                            port=self.settings['port'],
                            username=self.settings['username'])
            raise
    
    @log_operation(logger.logger)
    def upload(self, local_file_path: str, remote_filename: str) -> bool:
        """Upload a backup file to the SFTP server.
        
        Args:
            local_file_path: Path to the local file to upload
            remote_filename: Name to give the file on the remote server
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        try:
            with self._connect() as sftp:
                # Create remote directory if it doesn't exist
                if not sftp.exists(self.settings['remote_path']):
                    sftp.makedirs(self.settings['remote_path'])
                
                # Upload the file
                remote_path = os.path.join(self.settings['remote_path'], remote_filename)
                sftp.put(local_file_path, remote_path)
                
                # Get file size for logging
                size = sftp.stat(remote_path).st_size
                logger.logger.info("Backup file uploaded successfully",
                               source=local_file_path,
                               destination=remote_path,
                               size_bytes=size)
                return True
                
        except Exception as e:
            logger.logger.error("Failed to upload backup file",
                            error=str(e),
                            error_type=type(e).__name__,
                            source=local_file_path,
                            remote_path=self.settings['remote_path'])
            return False
    
    @log_operation(logger.logger)
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all backups on the SFTP server.
        
        Returns:
            List of dictionaries containing backup information
        """
        backups = []
        try:
            with self._connect() as sftp:
                if not sftp.exists(self.settings['remote_path']):
                    return []
                    
                for attr in sftp.listdir_attr(self.settings['remote_path']):
                    filename = attr.filename
                    if not filename.endswith('.bundle'):
                        continue
                        
                    timestamp = self._parse_backup_timestamp(filename)
                    if timestamp:
                        backups.append({
                            'filename': filename,
                            'timestamp': timestamp,
                            'size': attr.st_size
                        })
                
                logger.logger.info("Listed remote backups",
                               backup_count=len(backups))
                return backups
                
        except Exception as e:
            logger.logger.error("Failed to list remote backups",
                            error=str(e),
                            error_type=type(e).__name__,
                            remote_path=self.settings['remote_path'])
            return []
    
    @log_operation(logger.logger)
    def cleanup(self, retention_days: int) -> None:
        """Remove backup files older than retention_days from SFTP server.
        
        Args:
            retention_days: Number of days to keep backups for
        """
        try:
            now = datetime.now(timezone.utc)
            removed = 0
            
            with self._connect() as sftp:
                for backup in self.list_backups():
                    age = now - backup['timestamp'].replace(tzinfo=timezone.utc)
                    if age.days > retention_days:
                        remote_path = os.path.join(self.settings['remote_path'], backup['filename'])
                        sftp.remove(remote_path)
                        removed += 1
            
            logger.logger.info("Cleanup completed",
                           removed_count=removed,
                           retention_days=retention_days)
                    
        except Exception as e:
            logger.logger.error("Failed to cleanup old backups",
                            error=str(e),
                            error_type=type(e).__name__,
                            remote_path=self.settings['remote_path'])