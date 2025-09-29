"""
Shard failure recovery and cleanup for Shortlist.

This module handles cleanup of orphaned shard outputs and coordinates
recovery from partial shard failures.
"""

import os
import json
import glob
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class ShardOutput:
    """Information about a shard's output."""
    shard_id: str
    output_path: Path
    status: str  # 'complete', 'failed', 'orphaned'
    error: Optional[str] = None

class ShardRecoveryManager:
    """Manages recovery and cleanup of sharded task outputs."""
    
    def __init__(self, output_base_dir: str = "/app/output"):
        """Initialize the recovery manager.
        
        Args:
            output_base_dir: Base directory for task outputs
        """
        self.output_base_dir = Path(output_base_dir)
    
    def find_orphaned_shards(
        self,
        task_id: str,
        expected_shards: int
    ) -> List[ShardOutput]:
        """Find orphaned shard outputs for a task.
        
        Args:
            task_id: Parent task ID
            expected_shards: Expected number of shards
        
        Returns:
            List of orphaned shard outputs
        """
        # Check shard output directory
        shard_dir = self.output_base_dir / task_id / "shards"
        if not shard_dir.exists():
            return []
        
        # Find all shard outputs
        shard_pattern = f"{task_id}_shard_*"
        found_shards: Dict[str, ShardOutput] = {}
        
        for output_file in shard_dir.glob(shard_pattern):
            shard_id = output_file.stem.split('_')[-1]
            status_file = output_file.with_suffix('.status')
            
            if status_file.exists():
                with open(status_file) as f:
                    status_data = json.load(f)
                    status = status_data.get('status', 'orphaned')
                    error = status_data.get('error')
            else:
                status = 'orphaned'
                error = None
            
            found_shards[shard_id] = ShardOutput(
                shard_id=shard_id,
                output_path=output_file,
                status=status,
                error=error
            )
        
        # Find missing or orphaned shards
        orphaned = []
        for i in range(1, expected_shards + 1):
            shard_id = str(i)
            if shard_id not in found_shards:
                # Missing shard
                continue
            
            shard = found_shards[shard_id]
            if shard.status in ('orphaned', 'failed'):
                orphaned.append(shard)
        
        return orphaned
    
    def cleanup_orphaned_shards(
        self,
        task_id: str,
        dry_run: bool = False
    ) -> List[Path]:
        """Clean up orphaned shard outputs.
        
        Args:
            task_id: Parent task ID
            dry_run: If True, only report files to be deleted
        
        Returns:
            List of cleaned up file paths
        """
        shard_dir = self.output_base_dir / task_id / "shards"
        if not shard_dir.exists():
            return []
        
        # Find all orphaned files
        to_delete = []
        for file_path in shard_dir.glob("*"):
            if file_path.is_file():
                status_file = file_path.with_suffix('.status')
                if status_file.exists():
                    with open(status_file) as f:
                        status_data = json.load(f)
                        if status_data.get('status') in ('orphaned', 'failed'):
                            to_delete.extend([file_path, status_file])
                else:
                    # No status file = orphaned
                    to_delete.append(file_path)
        
        if not dry_run:
            for file_path in to_delete:
                try:
                    file_path.unlink()
                    logger.info("Deleted orphaned file",
                              file=str(file_path))
                except Exception as e:
                    logger.error("Failed to delete file",
                               file=str(file_path),
                               error=str(e))
        
        return to_delete
    
    def mark_shard_complete(
        self,
        task_id: str,
        shard_id: str,
        output_path: Path
    ) -> None:
        """Mark a shard as successfully completed.
        
        Args:
            task_id: Parent task ID
            shard_id: Shard ID
            output_path: Path to shard output
        """
        status_file = output_path.with_suffix('.status')
        status_data = {
            'status': 'complete',
            'shard_id': shard_id,
            'task_id': task_id
        }
        
        with open(status_file, 'w') as f:
            json.dump(status_data, f)
    
    def mark_shard_failed(
        self,
        task_id: str,
        shard_id: str,
        output_path: Path,
        error: str
    ) -> None:
        """Mark a shard as failed.
        
        Args:
            task_id: Parent task ID
            shard_id: Shard ID
            output_path: Path to shard output
            error: Error message
        """
        status_file = output_path.with_suffix('.status')
        status_data = {
            'status': 'failed',
            'shard_id': shard_id,
            'task_id': task_id,
            'error': error
        }
        
        with open(status_file, 'w') as f:
            json.dump(status_data, f)
    
    def check_shard_completion(
        self,
        task_id: str,
        expected_shards: int
    ) -> bool:
        """Check if all shards for a task completed successfully.
        
        Args:
            task_id: Parent task ID
            expected_shards: Expected number of shards
        
        Returns:
            True if all shards completed successfully
        """
        shard_dir = self.output_base_dir / task_id / "shards"
        if not shard_dir.exists():
            return False
        
        completed_shards = set()
        for status_file in shard_dir.glob("*.status"):
            with open(status_file) as f:
                status_data = json.load(f)
                if status_data.get('status') == 'complete':
                    completed_shards.add(status_data['shard_id'])
        
        return len(completed_shards) == expected_shards