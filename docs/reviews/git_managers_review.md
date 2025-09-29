# Git Managers Code Review

## Overview
The Shortlist project uses a modular Git management system with three implementations:
1. RealGitManager (git_manager.py) - Production implementation
2. MockGitManager (mock_git_manager.py) - Development/testing implementation
3. ChaosGitManager (chaos_git_manager.py) - Resilience testing implementation

This review focuses on error handling and retry logic across these implementations.

## Critical Issues

### 1. RealGitManager Error Handling

#### Problems Found:
1. No retry mechanism for transient failures
2. Basic error handling without specific error types
3. Insufficient error context in logs
4. No cleanup after failed operations

#### Current Implementation (git_manager.py):
```python
def sync(self) -> bool:
    try:
        self._run_command(['git', 'pull'])
        return True
    except subprocess.CalledProcessError:
        return False
```

#### Recommended Implementation:
```python
class GitOperationError(Exception):
    """Base exception for git operations"""
    pass

class GitNetworkError(GitOperationError):
    """Network-related git errors"""
    pass

class GitStateError(GitOperationError):
    """Repository state errors"""
    pass

def sync(self) -> bool:
    max_retries = 3
    retry_delay = 1.0  # Initial delay in seconds
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                self.logger.info("Retrying sync operation",
                               attempt=attempt + 1,
                               max_attempts=max_retries)
            
            # Check repository state
            if not self._is_repo_clean():
                raise GitStateError("Local changes present")
                
            output = self._run_command(['git', 'pull'])
            self.logger.info("Sync successful",
                           attempt=attempt + 1,
                           output=output)
            return True
            
        except subprocess.CalledProcessError as e:
            if self._is_network_error(e.stderr):
                error_type = GitNetworkError
            else:
                error_type = GitOperationError
                
            self.logger.warning("Sync attempt failed",
                              attempt=attempt + 1,
                              error=str(e),
                              stderr=e.stderr,
                              error_type=error_type.__name__)
                
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            
            self.logger.error("Sync failed after retries",
                            max_attempts=max_retries,
                            final_error=str(e))
            return False
```

### 2. Error Classification

#### Problem
Current implementation doesn't properly categorize errors, making retry decisions difficult.

#### Recommended Implementation:
```python
class GitErrorClassifier:
    """Classifies Git errors for proper handling"""
    
    NETWORK_ERRORS = [
        "Could not resolve host",
        "failed to connect",
        "Connection timed out",
        "Connection refused"
    ]
    
    LOCK_ERRORS = [
        "Unable to create",
        "index.lock",
        "is locked",
        "already exists"
    ]
    
    CONFLICT_ERRORS = [
        "conflict",
        "Your local changes",
        "would be overwritten",
        "Please commit your changes"
    ]
    
    @classmethod
    def classify_error(cls, error_msg: str) -> str:
        """Classify error message into error type"""
        error_msg = error_msg.lower()
        
        if any(err in error_msg for err in cls.NETWORK_ERRORS):
            return "network"
        elif any(err in error_msg for err in cls.LOCK_ERRORS):
            return "lock"
        elif any(err in error_msg for err in cls.CONFLICT_ERRORS):
            return "conflict"
        return "unknown"
    
    @classmethod
    def is_retryable(cls, error_type: str) -> bool:
        """Determine if error type is retryable"""
        return error_type in ["network", "lock"]
```

### 3. Transaction Management

#### Problem
No transactional safety for multi-step Git operations.

#### Recommended Implementation:
```python
class GitTransaction:
    """Manages atomic Git operations"""
    
    def __init__(self, git_manager):
        self.git_manager = git_manager
        self.operations = []
        self.state_before = None
    
    def __enter__(self):
        # Save current state
        self.state_before = {
            "branch": self._get_current_branch(),
            "head": self._get_head_commit()
        }
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Rollback on error
            self._rollback()
    
    def _rollback(self):
        """Rollback to previous state"""
        if self.state_before:
            self.git_manager._run_command(
                ["git", "reset", "--hard", self.state_before["head"]]
            )
            self.git_manager._run_command(
                ["git", "checkout", self.state_before["branch"]]
            )
```

### 4. Resource Management

#### Problem
Resource cleanup is inconsistent across implementations.

#### Recommended Implementation:
```python
class GitResourceManager:
    """Manages Git operation resources"""
    
    def __init__(self):
        self.locks = set()
        self.temp_files = set()
    
    def acquire_lock(self, lock_path: str) -> bool:
        """Acquire a Git lock file"""
        if not self._try_create_lock(lock_path):
            return False
        self.locks.add(lock_path)
        return True
    
    def cleanup(self):
        """Clean up all resources"""
        for lock in self.locks:
            self._remove_lock(lock)
        for temp_file in self.temp_files:
            self._remove_temp_file(temp_file)
```

## Implementation Priorities

1. Add Retry Mechanism
   - Implement exponential backoff
   - Add error classification
   - Configure retry policies

2. Enhance Error Handling
   - Add specific error types
   - Improve error logging
   - Add cleanup mechanisms

3. Add Transaction Support
   - Implement GitTransaction
   - Add rollback capability
   - Handle cleanup

4. Improve Resource Management
   - Add resource tracking
   - Implement cleanup
   - Handle edge cases

## Security Considerations

1. Authentication
   - Secure credential handling
   - Token rotation
   - Access logging

2. Data Protection
   - Safe error messages
   - Secure temp files
   - Clean file cleanup

3. Operation Safety
   - Validate commands
   - Check permissions
   - Verify state changes

## Testing Strategy

1. Error Handling Tests
   - Test each error type
   - Verify retry behavior
   - Check cleanup

2. Integration Tests
   - Test with real Git
   - Test network issues
   - Test concurrent access

3. Performance Tests
   - Measure retry impact
   - Test resource usage
   - Check cleanup timing

## Next Steps

1. Implement GitErrorClassifier
2. Add retry mechanism to RealGitManager
3. Add transaction support
4. Enhance resource management
5. Improve error logging
6. Add comprehensive tests

## Code Examples

### Retry Mechanism
```python
def with_retries(max_retries=3, initial_delay=1.0):
    """Decorator for retryable Git operations"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except GitOperationError as e:
                    last_error = e
                    
                    if not GitErrorClassifier.is_retryable(e.error_type):
                        raise
                    
                    if attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)
                        self.logger.warning("Operation failed, retrying",
                                         error=str(e),
                                         attempt=attempt + 1,
                                         delay=delay)
                        time.sleep(delay)
                        continue
            
            raise last_error
        return wrapper
    return decorator
```

### Error Handling
```python
class SafeGitOperation:
    """Context manager for safe Git operations"""
    
    def __init__(self, manager, operation_name):
        self.manager = manager
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.manager.logger.info(f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            self.manager.logger.info(
                f"Completed {self.operation_name}",
                duration=duration
            )
        else:
            self.manager.logger.error(
                f"Failed {self.operation_name}",
                error=str(exc_val),
                error_type=exc_type.__name__,
                duration=duration
            )
```

### Resource Management
```python
class GitLockManager:
    """Manages Git lock files"""
    
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.locks = {}
    
    def acquire(self, lock_name, timeout=10):
        lock_path = os.path.join(self.repo_path, f".git/{lock_name}.lock")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                self.locks[lock_name] = (lock_path, fd)
                return True
            except FileExistsError:
                time.sleep(0.1)
        return False
    
    def release(self, lock_name):
        if lock_name in self.locks:
            lock_path, fd = self.locks[lock_name]
            os.close(fd)
            os.unlink(lock_path)
            del self.locks[lock_name]
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for lock_name in list(self.locks.keys()):
            self.release(lock_name)
```