# Node.py Code Review

## Overview
This review focuses on thread safety and state management issues in the `node.py` module, which implements a distributed task assignment and execution system using a state machine pattern.

## Critical Issues

### 1. File Access Race Conditions

#### Problem
Multiple nodes can simultaneously attempt to read and write shared JSON files (roster.json, assignments.json, schedule.json) without proper synchronization.

#### Specific Instances:
- Lines 446-448: Reading assignments file during claim attempt
- Lines 466-468: Writing assignments file during claim
- Lines 597-599: Writing roster file during heartbeat

#### Impact
This can lead to:
- Lost updates when multiple nodes write simultaneously
- Inconsistent state when reading partially written files
- Potential file corruption

### 2. Git Operation Race Conditions

#### Problem
Git operations are not atomic and can conflict when multiple nodes perform them simultaneously.

#### Specific Instances:
- Lines 401, 444: Multiple git pulls before state transitions
- Line 602: Commit and push during roster heartbeat
- Line 535: Commit and push during task heartbeat

#### Impact
- Failed pushes due to concurrent updates
- Potential loss of node state information
- Inconsistent cluster state

### 3. State Management Issues

#### Problem
The state machine lacks proper validation and protection against invalid state transitions.

#### Specific Instances:
- Lines 427-428: Direct state modification without validation
- Lines 454, 476: State transitions without cleanup
- Line 552: State reset without proper resource cleanup

#### Impact
- Potential state corruption
- Resource leaks
- Inconsistent node behavior

### 4. Docker Resource Management

#### Problem
Docker container lifecycle management lacks proper cleanup in error cases.

#### Specific Instances:
- Lines 488-492: Container startup without guaranteed cleanup
- Lines 540, 547: Container cleanup in try/except blocks
- Line 268: Container stop without proper error handling

#### Impact
- Potential resource leaks
- Orphaned containers
- System resource exhaustion

## Recommendations

### 1. File Access Synchronization
```python
# Add file-based locking mechanism
class FileLock:
    def __init__(self, file_path):
        self.lock_path = f"{file_path}.lock"
        self.file_path = file_path
        
    def __enter__(self):
        while True:
            try:
                with open(self.lock_path, 'x') as f:
                    f.write(str(os.getpid()))
                return self
            except FileExistsError:
                time.sleep(0.1)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.unlink(self.lock_path)
        except FileNotFoundError:
            pass

# Usage:
with FileLock(ASSIGNMENTS_FILE):
    # Read/write operations here
```

### 2. Git Operation Retries
```python
def git_operation_with_retry(operation, max_retries=3):
    for attempt in range(max_retries):
        try:
            return operation()
        except subprocess.CalledProcessError:
            if attempt == max_retries - 1:
                raise
            time.sleep(random.uniform(1, 3))
            git_pull()  # Sync before retry
```

### 3. State Machine Validation
```python
class StateTransition:
    def __init__(self, from_state, to_state, validation_fn=None, cleanup_fn=None):
        self.from_state = from_state
        self.to_state = to_state
        self.validation_fn = validation_fn
        self.cleanup_fn = cleanup_fn

    def execute(self, node):
        if self.validation_fn and not self.validation_fn(node):
            raise InvalidStateTransition(f"Cannot transition from {self.from_state} to {self.to_state}")
        if self.cleanup_fn:
            self.cleanup_fn(node)
        node.state = self.to_state
```

### 4. Resource Management
```python
class ResourceManager:
    def __init__(self):
        self.active_resources = {}
        
    def register(self, resource_id, cleanup_fn):
        self.active_resources[resource_id] = cleanup_fn
        
    def cleanup(self, resource_id):
        if resource_id in self.active_resources:
            self.active_resources[resource_id]()
            del self.active_resources[resource_id]
    
    def cleanup_all(self):
        for cleanup_fn in self.active_resources.values():
            cleanup_fn()
        self.active_resources.clear()
```

## Implementation Priority

1. Add file locking for critical file operations to prevent data corruption
2. Implement proper state transition validation
3. Add retries for git operations
4. Enhance resource cleanup mechanisms

## Security Considerations

- File locks should have timeouts to prevent deadlocks
- Git operation retries should have exponential backoff
- Resource cleanup should be guaranteed even on crash
- State transitions should be logged for audit purposes

## Testing Strategy

1. Add unit tests for state transitions
2. Add integration tests for file locking
3. Add stress tests for concurrent operations
4. Add chaos testing for resource cleanup

## Next Steps

1. Create isolated testing environment
2. Implement file locking mechanism
3. Add state transition validation
4. Enhance resource management
5. Add comprehensive testing suite