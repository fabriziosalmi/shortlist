# Shortlist Disaster Recovery

The Shortlist system includes a robust disaster recovery system through the `archiver` renderer, which provides automated repository backups to multiple storage locations.

## Overview

The archiver renderer:
- Creates complete Git bundle backups of the repository
- Supports multiple storage backends (local filesystem, SFTP)
- Configurable backup schedules using cron expressions
- Automatic cleanup of old backups based on retention policies
- Structured logging for tracking backup operations

## Configuration

Backup jobs are configured in `schedule.json` under the `system_archiver` task:

```json
{
  "id": "system_archiver",
  "type": "archiver",
  "priority": 99,
  "config": {
    "jobs": [
      {
        "id": "daily_local_backup",
        "enabled": true,
        "schedule": "0 3 * * *",    // Daily at 3 AM
        "retention_days": 7,         // Keep backups for 7 days
        "storage_backend": "local",
        "settings": {
          "path": "/backups/shortlist"
        }
      },
      {
        "id": "weekly_sftp_offsite_backup",
        "enabled": true,
        "schedule": "0 5 * * 0",    // Weekly on Sunday at 5 AM
        "retention_days": 30,        // Keep backups for 30 days
        "storage_backend": "sftp",
        "settings": {
          "host": "backup.example.com",
          "port": 22,
          "username": "shortlist_bot",
          "remote_path": "/offsite/shortlist"
        }
      }
    ]
  }
}
```

### Job Configuration Options

- `id`: Unique identifier for the backup job
- `enabled`: Whether the job is active (default: true)
- `schedule`: Cron expression for backup timing
- `retention_days`: Number of days to keep backups
- `storage_backend`: Storage system to use ("local" or "sftp")
- `settings`: Backend-specific configuration

## Storage Backends

### Local Backend
Stores backups in a local directory.

Settings:
- `path`: Absolute path to backup directory

### SFTP Backend
Stores backups on a remote SFTP server.

Settings:
- `host`: SFTP server hostname
- `port`: SFTP port (default: 22)
- `username`: SFTP username
- `remote_path`: Absolute path on remote server

Authentication:
- Password: Set `SFTP_PASSWORD` environment variable
- SSH Key: Set `SFTP_PRIVATE_KEY_PATH` environment variable

## Backup Format

Backups are created using `git bundle` and follow the naming format:
```
shortlist-backup-YYYYMMDDTHHmmssZ.bundle
```

For example: `shortlist-backup-20250929T030000Z.bundle`

Each bundle is a complete, self-contained Git repository that can be cloned or fetched from.

## Disaster Recovery Procedure

### From Local Backup

1. Locate the latest backup bundle in your backup directory:
   ```bash
   ls -lt /backups/shortlist/shortlist-backup-*.bundle
   ```

2. Create a new repository from the bundle:
   ```bash
   git clone /backups/shortlist/shortlist-backup-20250929T030000Z.bundle recovered-shortlist
   cd recovered-shortlist
   ```

### From SFTP Backup

1. Download the latest backup bundle from SFTP:
   ```bash
   sftp shortlist_bot@backup.example.com
   cd /offsite/shortlist
   get shortlist-backup-20250929T030000Z.bundle
   ```

2. Create a new repository from the bundle:
   ```bash
   git clone shortlist-backup-20250929T030000Z.bundle recovered-shortlist
   cd recovered-shortlist
   ```

### Post-Recovery Steps

1. Update remote origin:
   ```bash
   git remote set-url origin <your-repository-url>
   ```

2. Push to new repository:
   ```bash
   git push -u origin main
   ```

## Monitoring Backups

The archiver renderer uses structured logging. All backup operations are logged to `/app/data/archiver.log` with detailed information including:
- Backup timing
- File sizes
- Success/failure status
- Error details if failures occur

Example log entry:
```json
{
  "timestamp": "2025-09-29T03:00:00Z",
  "level": "INFO",
  "message": "Backup file uploaded successfully",
  "logger": "archiver_renderer",
  "job_id": "daily_local_backup",
  "source": "/tmp/shortlist-backup-20250929T030000Z.bundle",
  "destination": "/backups/shortlist/shortlist-backup-20250929T030000Z.bundle",
  "size_bytes": 1234567
}
```

## Adding New Storage Backends

The archiver system is designed to be extensible. To add a new storage backend:

1. Create a new class in `renderers/archiver/backends/` that inherits from `StorageBackend`
2. Implement the required methods:
   - `upload()`
   - `list_backups()`
   - `cleanup()`
3. Add the backend to `STORAGE_BACKENDS` in `main.py`
4. Update this documentation with the new backend's configuration options

## Best Practices

1. Configure at least one local and one remote backup job
2. Set appropriate retention periods based on your needs
3. Use SSH keys instead of passwords for SFTP authentication
4. Monitor the archiver logs regularly
5. Periodically test the recovery procedure
6. Keep SSH keys and SFTP credentials securely stored