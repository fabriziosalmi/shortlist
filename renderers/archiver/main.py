"""
Main archiver renderer for disaster recovery backups.
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
import time
from typing import Dict, Any, Optional
from croniter import croniter

from utils.logging_config import configure_logging
from utils.logging_utils import ComponentLogger, RENDERER_CONTEXT, log_operation

from backends.local import LocalBackend
from backends.sftp import SFTPBackend

# Configure logging
configure_logging('archiver_renderer', log_level="INFO", log_file='/app/data/archiver.log')
logger = ComponentLogger('archiver_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='archiver')

# Storage backend registry
STORAGE_BACKENDS = {
    'local': LocalBackend,
    'sftp': SFTPBackend
}

class ArchiverJob:
    """Represents a configured backup job."""
    
    def __init__(self, job_config: Dict[str, Any]) -> None:
        """Initialize a backup job from configuration.
        
        Args:
            job_config: Job configuration dictionary
        """
        self.id = job_config['id']
        self.enabled = job_config.get('enabled', True)
        self.schedule = job_config['schedule']
        self.retention_days = job_config.get('retention_days', 7)
        self.storage_backend = job_config['storage_backend']
        self.settings = job_config['settings']
        
        # Initialize storage backend
        if self.storage_backend not in STORAGE_BACKENDS:
            raise ValueError(f"Unknown storage backend: {self.storage_backend}")
        
        self.backend = STORAGE_BACKENDS[self.storage_backend](self.settings)
        self.last_run = None
        
        logger.logger.info("Initialized backup job",
                       job_id=self.id,
                       backend=self.storage_backend,
                       schedule=self.schedule,
                       retention_days=self.retention_days)
    
    def should_run(self) -> bool:
        """Check if this job should run now based on its schedule."""
        now = datetime.now(timezone.utc)
        cron = croniter(self.schedule, self.last_run or now)
        next_run = cron.get_next(datetime)
        return now >= next_run
    
    @log_operation(logger.logger)
    def run(self, repo_path: str) -> bool:
        """Execute the backup job.
        
        Args:
            repo_path: Path to the Git repository to backup
            
        Returns:
            bool: True if backup was successful
        """
        if not self.enabled:
            logger.logger.info("Skipping disabled job", job_id=self.id)
            return False
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bundle_name = f"shortlist-backup-{timestamp}.bundle"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = os.path.join(temp_dir, bundle_name)
            
            try:
                # Create Git bundle
                logger.logger.info("Creating Git bundle",
                               bundle_path=bundle_path)
                
                result = subprocess.run(
                    ['git', 'bundle', 'create', bundle_path, '--all'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Upload bundle
                if self.backend.upload(bundle_path, bundle_name):
                    self.last_run = datetime.now(timezone.utc)
                    
                    # Cleanup old backups
                    self.backend.cleanup(self.retention_days)
                    return True
                    
                return False
                
            except subprocess.CalledProcessError as e:
                logger.logger.error("Failed to create Git bundle",
                               error=e.stderr,
                               error_type=type(e).__name__,
                               command=' '.join(e.cmd))
                return False
                
            except Exception as e:
                logger.logger.error("Backup job failed",
                               error=str(e),
                               error_type=type(e).__name__,
                               job_id=self.id)
                return False

def read_config() -> Optional[Dict[str, Any]]:
    """Read the task configuration file."""
    try:
        with open('/app/data/task_config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.logger.error("Failed to read task configuration",
                       error=str(e),
                       error_type=type(e).__name__)
        return None

def main() -> None:
    """Main archiver renderer loop."""
    logger.log_startup()
    
    # Read job configurations
    config = read_config()
    if not config or 'jobs' not in config:
        logger.logger.error("Invalid or missing configuration")
        return
    
    # Initialize backup jobs
    jobs = []
    for job_config in config['jobs']:
        try:
            jobs.append(ArchiverJob(job_config))
        except Exception as e:
            logger.logger.error("Failed to initialize backup job",
                           error=str(e),
                           error_type=type(e).__name__,
                           job_config=job_config)
    
    if not jobs:
        logger.logger.error("No valid backup jobs configured")
        return
    
    logger.logger.info("Archiver ready",
                   jobs_count=len(jobs))
    
    # Main loop
    while True:
        for job in jobs:
            if job.should_run():
                job.run('/app/data')
        
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()