import json
import os
import subprocess
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

class GitManager(ABC):
    """Base class for Git operations management."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the git manager.
        
        Args:
            logger: Optional logger instance. If not provided, a default one will be created.
        """
        self.logger = logger or logging.getLogger(__name__)
    
    @abstractmethod
    def sync(self) -> bool:
        """Sync the local state with the remote state.
        
        Returns:
            bool: True if sync succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    def commit_and_push(self, files: List[str], message: str) -> bool:
        """Commit changes and push to remote.
        
        Args:
            files: List of files to commit
            message: Commit message
            
        Returns:
            bool: True if push succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    def read_file(self, path: Union[str, Path]) -> str:
        """Read a file's contents.
        
        Args:
            path: Path to the file
            
        Returns:
            str: The file's contents
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            IOError: If the file can't be read
        """
        pass
    
    @abstractmethod
    def write_file(self, path: Union[str, Path], content: str) -> None:
        """Write content to a file.
        
        Args:
            path: Path to the file
            content: Content to write
            
        Raises:
            IOError: If the file can't be written
        """
        pass
    
    @abstractmethod
    def read_json(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Read and parse a JSON file.
        
        Args:
            path: Path to the JSON file
            
        Returns:
            dict: Parsed JSON data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file isn't valid JSON
        """
        pass
    
    @abstractmethod
    def write_json(self, path: Union[str, Path], data: Dict[str, Any]) -> None:
        """Write data as JSON to a file.
        
        Args:
            path: Path to the file
            data: Data to write as JSON
            
        Raises:
            IOError: If the file can't be written
            TypeError: If the data isn't JSON-serializable
        """
        pass

class RealGitManager(GitManager):
    """Concrete implementation for real Git operations."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
    
    def _run_command(self, command: List[str], suppress_errors: bool = False) -> str:
        """Run a shell command safely.
        
        Args:
            command: Command and arguments as list
            suppress_errors: Whether to suppress error raising
            
        Returns:
            str: Command output
            
        Raises:
            subprocess.CalledProcessError: If command fails and errors not suppressed
        """
        try:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                encoding='utf-8'
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                self.logger.error("Command execution failed",
                             command=' '.join(command),
                             stderr=e.stderr,
                             exit_code=e.returncode)
                raise
            return ''
    
    def sync(self) -> bool:
        """Pull latest changes from remote."""
        try:
            self._run_command(['git', 'pull'])
            return True
        except subprocess.CalledProcessError:
            return False
    
    def commit_and_push(self, files: List[str], message: str) -> bool:
        """Commit and push changes."""
        try:
            self._run_command(['git', 'add'] + files)
            # Check if there are changes to commit
            status = self._run_command(['git', 'status', '--porcelain'])
            if any(file in status for file in files):
                self._run_command(['git', 'commit', '-m', message])
                self._run_command(['git', 'push'])
                return True
            return False
        except subprocess.CalledProcessError:
            return False
    
    def read_file(self, path: Union[str, Path]) -> str:
        """Read a file's contents from disk."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_text(encoding='utf-8')
    
    def write_file(self, path: Union[str, Path], content: str) -> None:
        """Write content to a file on disk."""
        path = Path(path)
        path.write_text(content, encoding='utf-8')
    
    def read_json(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Read and parse a JSON file from disk."""
        content = self.read_file(path)
        return json.loads(content)
    
    def write_json(self, path: Union[str, Path], data: Dict[str, Any]) -> None:
        """Write data as JSON to disk."""
        content = json.dumps(data, indent=2)
        self.write_file(path, content)