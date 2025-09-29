import json
import copy
import random
import logging
from pathlib import Path
from typing import Dict, List, Any, Union, Optional

from .git_manager import GitManager

# Initial state for new repositories
INITIAL_STATE = {
    "roster.json": json.dumps({
        "nodes": []
    }, indent=2),
    "schedule.json": json.dumps({
        "tasks": [
            {"id": "system_governor", "type": "governor", "priority": -2},
            {"id": "system_healer", "type": "healer", "priority": -1},
            {"id": "shortlist_admin_ui", "type": "admin_ui", "priority": 1},
            {"id": "shortlist_dashboard", "type": "dashboard", "priority": 2}
        ]
    }, indent=2),
    "assignments.json": json.dumps({
        "assignments": {}
    }, indent=2),
    "shortlist.json": json.dumps({
        "items": [
            "Welcome to Shortlist (in-memory mode)",
            "This is a simulated repository for fast local development"
        ]
    }, indent=2)
}

class MockGitManager(GitManager):
    """Mock implementation of GitManager for fast local development.
    
    All operations are performed in memory without touching the filesystem
    or making network calls. This is perfect for development and testing.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        # Initialize state
        self.remote_state = copy.deepcopy(INITIAL_STATE)
        self.local_state = copy.deepcopy(INITIAL_STATE)
        self.logger.info("🚀 Initialized in-memory Git manager",
                      files=list(self.remote_state.keys()))
    
    def sync(self) -> bool:
        """Simulate git pull by copying remote state to local."""
        self.logger.debug("📥 [IN-MEMORY] Syncing from remote")
        self.local_state = copy.deepcopy(self.remote_state)
        return True
    
    def commit_and_push(self, files: List[str], message: str) -> bool:
        """Simulate git commit and push by copying local state to remote."""
        # Simulate network issues and conflicts (10% chance of failure)
        if random.random() < 0.1:
            self.logger.warning("📡 [IN-MEMORY] Push failed (simulated network issue)",
                            files=files)
            return False
            
        try:
            # Update remote state with local changes
            for file in files:
                if file not in self.local_state:
                    self.logger.warning("🔍 [IN-MEMORY] File not found in local state",
                                    file=file)
                    continue
                self.remote_state[file] = self.local_state[file]
            
            self.logger.info("📤 [IN-MEMORY] Pushed changes",
                         message=message,
                         files=files)
            return True
            
        except Exception as e:
            self.logger.error("❌ [IN-MEMORY] Push failed",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def read_file(self, path: Union[str, Path]) -> str:
        """Read a file from local state."""
        path_str = str(Path(path).name)  # Get just the filename
        if path_str not in self.local_state:
            raise FileNotFoundError(f"[IN-MEMORY] File not found: {path_str}")
        return self.local_state[path_str]
    
    def write_file(self, path: Union[str, Path], content: str) -> None:
        """Write a file to local state."""
        path_str = str(Path(path).name)  # Get just the filename
        self.local_state[path_str] = content
        self.logger.debug("✍️ [IN-MEMORY] Updated file",
                       file=path_str,
                       size=len(content))
    
    def read_json(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Read and parse a JSON file from local state."""
        content = self.read_file(path)
        return json.loads(content)
    
    def write_json(self, path: Union[str, Path], data: Dict[str, Any]) -> None:
        """Write data as JSON to local state."""
        content = json.dumps(data, indent=2)
        self.write_file(path, content)
    
    def __str__(self) -> str:
        """String representation showing current state."""
        return f"MockGitManager(files={list(self.local_state.keys())})"