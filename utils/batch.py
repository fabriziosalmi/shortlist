"""
Batch operation manager for Shortlist.

This module provides functionality for batching multiple changes
into a single Git commit, reducing write traffic and noise.
"""

import json
import os
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

@dataclass
class BatchOperation:
    """Represents a pending file operation in a batch."""
    file_path: str
    content: Any
    description: str

@dataclass
class BatchManager:
    """Manages batched operations with Git.
    
    This class accumulates changes to be made and commits them
    all at once, reducing Git write operations.
    """
    
    git_manager: Any  # GitManager instance
    operations: List[BatchOperation] = field(default_factory=list)
    modified_files: Set[str] = field(default_factory=set)
    base_path: str = ""
    
    def __post_init__(self):
        """Initialize the batch manager."""
        self.file_cache: Dict[str, Any] = {}
    
    def read_json(self, file_path: str) -> Dict[str, Any]:
        """Read a JSON file, using cache if available.
        
        Args:
            file_path: Path to the JSON file
        
        Returns:
            Parsed JSON content
        """
        abs_path = os.path.join(self.base_path, file_path)
        
        # Return cached version if we have it
        if abs_path in self.file_cache:
            return deepcopy(self.file_cache[abs_path])
        
        # Read from Git/disk
        content = self.git_manager.read_json(file_path)
        self.file_cache[abs_path] = deepcopy(content)
        return content
    
    def stage_json_update(
        self,
        file_path: str,
        content: Dict[str, Any],
        description: str
    ) -> None:
        """Stage a JSON file update for the next batch commit.
        
        Args:
            file_path: Path to the JSON file
            content: New content to write
            description: Description of the change
        """
        abs_path = os.path.join(self.base_path, file_path)
        
        # Update cache
        self.file_cache[abs_path] = deepcopy(content)
        
        # Stage operation
        self.operations.append(
            BatchOperation(
                file_path=file_path,
                content=content,
                description=description
            )
        )
        self.modified_files.add(file_path)
        
        logger.debug("Staged JSON update",
                    file=file_path,
                    description=description)
    
    def has_changes(self) -> bool:
        """Check if there are pending changes in the batch."""
        return len(self.operations) > 0
    
    def commit(self, message: Optional[str] = None) -> bool:
        """Commit all batched changes.
        
        Args:
            message: Optional commit message. If not provided,
                    will be constructed from operation descriptions.
        
        Returns:
            True if commit succeeded
        """
        if not self.has_changes():
            return True
        
        try:
            # Write all files
            for op in self.operations:
                self.git_manager.write_json(op.file_path, op.content)
            
            # Generate commit message if none provided
            if not message:
                if len(self.operations) == 1:
                    message = self.operations[0].description
                else:
                    message = f"Batch update ({len(self.operations)} changes):\n" + \
                             "\n".join(f"- {op.description}" for op in self.operations)
            
            # Commit and push
            success = self.git_manager.commit_and_push(
                list(self.modified_files),
                message
            )
            
            if success:
                logger.info("Batch committed successfully",
                          files=list(self.modified_files),
                          changes_count=len(self.operations))
            else:
                logger.error("Failed to commit batch",
                           files=list(self.modified_files))
            
            return success
            
        finally:
            # Clear batch state
            self.operations.clear()
            self.modified_files.clear()
    
    def __enter__(self) -> 'BatchManager':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit.
        
        Automatically commits any pending changes unless an error occurred.
        """
        if exc_type is None and self.has_changes():
            self.commit()