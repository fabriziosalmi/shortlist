# Renderer Resource Management Review

## Overview
This review examines resource handling and cleanup mechanisms in the renderer modules of the shortlist project. The analysis focuses on three key renderers: governor, API, and dashboard, which represent different types of services in the system.

## Critical Areas

### 1. File Descriptor Management

#### API Renderer
**Issues Found:**
- No explicit file descriptor cleanup in secret management functions (`_read_secrets`, `_write_secrets`)
- Temporary file cleanup in `/v1/admin/preview` endpoint lacks error handling
- File handles in git operations might not be properly closed in error cases

**Recommendations:**
```python
def safe_file_operation(file_path: str, operation_fn):
    """Context manager for safe file operations with proper cleanup"""
    try:
        with open(file_path, mode) as f:
            return operation_fn(f)
    except Exception as e:
        logger.error(f"File operation failed: {str(e)}")
        raise
```

### 2. Container Resource Management

#### API Renderer Issues
- Docker containers in preview generation don't have resource limits
- No timeout mechanism for container operations
- Container cleanup might fail silently in error cases

**Recommendations:**
```python
def run_container_with_limits(config: dict):
    """Run container with resource limits and proper cleanup"""
    cmd = [
        "docker", "run",
        "--rm",  # Auto-remove container
        "--memory", "512m",  # Memory limit
        "--cpus", "0.5",    # CPU limit
        "--network", "none" # Network isolation for renderers
    ]
    try:
        result = subprocess.run(cmd, timeout=300)  # 5 minute timeout
        return result
    except subprocess.TimeoutExpired:
        # Cleanup any hanging containers
        container_id = get_container_id()
        if container_id:
            subprocess.run(["docker", "kill", container_id])
        raise
```

### 3. Memory Management

#### Governor Renderer
**Issues Found:**
- No limits on JSON data size in file operations
- Memory usage in git operations not monitored
- Large data structures not cleaned up promptly

**Recommendations:**
```python
def read_json_with_limits(file_path: str, max_size: int = 10 * 1024 * 1024):
    """Read JSON file with size limits"""
    if os.path.getsize(file_path) > max_size:
        raise ValueError(f"File exceeds maximum size of {max_size} bytes")
    with open(file_path, 'r') as f:
        return json.load(f)
```

### 4. Network Resource Management

#### Dashboard Renderer
**Issues Found:**
- No request rate limiting
- No timeout on file read operations
- No maximum client connection limit

**Recommendations:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/api/status')
@limiter.limit("1 per second")  # Rate limit
def api_status():
    with timeout(seconds=5):  # Operation timeout
        status_data = collect_status()
    return jsonify(status_data)
```

## Implementation Priorities

1. Container Resource Management
   - Add resource limits to all container operations
   - Implement proper cleanup mechanisms
   - Add timeouts to prevent hanging operations

2. File Handling
   - Implement proper file descriptor management
   - Add size limits to file operations
   - Ensure cleanup in error cases

3. Memory Management
   - Add data size limits
   - Implement cleanup of large data structures
   - Monitor memory usage in long-running operations

4. Network Resources
   - Implement rate limiting
   - Add request timeouts
   - Add connection limits

## Security Considerations

1. Container Security
   - Add read-only filesystem where possible
   - Restrict network access
   - Drop unnecessary capabilities

2. File Operations
   - Validate file paths
   - Implement proper permissions
   - Add virus scanning for uploads

3. API Security
   - Rate limiting
   - Input validation
   - Authentication timeout

## Testing Strategy

1. Resource Leak Tests
   - Long-running tests to detect memory leaks
   - File descriptor counting tests
   - Container cleanup verification

2. Load Tests
   - High concurrency tests
   - Large file handling tests
   - Network stress tests

3. Error Recovery Tests
   - Forced error injection
   - Resource cleanup verification
   - System recovery validation

## Next Steps

1. Update container configurations with resource limits
2. Implement robust cleanup mechanisms
3. Add monitoring for resource usage
4. Implement rate limiting
5. Add comprehensive error handling
6. Update documentation with resource guidelines

## Code Examples

### Container Resource Management
```python
class ResourceManagedContainer:
    def __init__(self, image: str, resources: Dict[str, str]):
        self.image = image
        self.resources = resources
        self.container_id = None

    def __enter__(self):
        cmd = ["docker", "run", "-d"]
        # Add resource limits
        cmd.extend(["--memory", self.resources["memory"]])
        cmd.extend(["--cpus", self.resources["cpus"]])
        # Add security options
        cmd.extend(["--read-only"])
        cmd.extend(["--security-opt", "no-new-privileges"])
        # Run container
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.container_id = result.stdout.strip()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.container_id:
            subprocess.run(["docker", "stop", self.container_id])
            subprocess.run(["docker", "rm", self.container_id])
```

### File Resource Management
```python
class SafeFileManager:
    def __init__(self, path: str, max_size: int = 10 * 1024 * 1024):
        self.path = path
        self.max_size = max_size
        self.file = None

    def __enter__(self):
        if os.path.exists(self.path) and os.path.getsize(self.path) > self.max_size:
            raise ValueError(f"File exceeds size limit of {self.max_size} bytes")
        self.file = open(self.path, 'r')
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()
```

### Network Resource Management
```python
def rate_limited_endpoint(func):
    def wrapper(*args, **kwargs):
        client_ip = request.remote_addr
        if rate_limiter.is_rate_limited(client_ip):
            raise HTTPException(status_code=429, detail="Too many requests")
        return func(*args, **kwargs)
    return wrapper
```