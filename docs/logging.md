# Structured Logging System

This document describes the structured logging system implemented across the Shortlist components.

## Overview

The logging system provides:
- JSON-formatted log output for better parsing and analysis
- Consistent logging patterns across all components
- Context-aware logging with component-specific information
- Performance tracking and execution timing
- State change tracking
- Error handling with stack traces

## Basic Usage

```python
from utils.logging_config import get_logger
from utils.logging_utils import log_execution_time, log_operation

# Get a logger for your component
logger = get_logger('my_component')

# Add persistent context
logger.add_context(component_type='renderer', renderer_name='web')

# Basic logging
logger.info('Processing started', task_id='123')
logger.error('Processing failed', error='Invalid input')

# Temporary context
with logger.context_bind(batch_id='456'):
    logger.info('Processing batch')  # Will include batch_id

# Track execution time
@log_execution_time(logger)
def process_data():
    # Function code here
    pass

# Log operations with timing
with log_operation(logger, 'data_processing', dataset='users'):
    process_data()
```

## Component Logger

For components that need standard logging patterns:

```python
from utils.logging_utils import ComponentLogger, RENDERER_CONTEXT

class WebRenderer(ComponentLogger):
    def __init__(self):
        super().__init__('web_renderer')
        self.logger.add_context(**RENDERER_CONTEXT)
        
    def start(self):
        self.log_startup(port=8080)
        # Component initialization
        
    def stop(self):
        self.log_shutdown(status='clean')
        # Component cleanup
```

## Log Format

All logs are output in JSON format with standard fields:

```json
{
    "timestamp": "2025-09-28T19:57:31.123Z",
    "level": "INFO",
    "message": "Processing started",
    "logger": "web_renderer",
    "hostname": "server1",
    "thread": "MainThread",
    "module": "renderer",
    "function": "process_data",
    "line": 42,
    "component_type": "renderer",
    "renderer_name": "web",
    "task_id": "123"
}
```

## Common Context

Predefined contexts are available for different component types:

- `NODE_CONTEXT`: For core node components
- `RENDERER_CONTEXT`: For content renderers
- `GOVERNOR_CONTEXT`: For the governor component
- `HEALER_CONTEXT`: For the healer component

## Best Practices

1. **Use Structured Fields**
   ```python
   # Good
   logger.info("Task processed", task_id=123, status="success")
   # Avoid
   logger.info(f"Task {task_id} processed with status {status}")
   ```

2. **Use Context Managers**
   ```python
   with log_operation(logger, "data_processing"):
       # Complex operation here
       pass
   ```

3. **Track State Changes**
   ```python
   log_state_change(logger, "task_status", old_state="pending", new_state="running")
   ```

4. **Include Relevant Context**
   ```python
   logger.add_context(
       node_id=node.id,
       component_version="1.2.3"
   )
   ```

5. **Use Error Context**
   ```python
   try:
       process_data()
   except Exception as e:
       logger.error("Data processing failed", error=str(e))
       raise
   ```

## Log Levels

- `DEBUG`: Detailed information for debugging
- `INFO`: General operational information
- `WARNING`: Minor issues that don't affect operation
- `ERROR`: Serious issues that affect operation
- `CRITICAL`: System-wide failures

## Configuration

The logging system can be configured per component:

```python
from utils.logging_config import configure_logging

configure_logging(
    component_name='web_renderer',
    log_level='INFO',
    log_file='/var/log/shortlist/web_renderer.log'
)
```