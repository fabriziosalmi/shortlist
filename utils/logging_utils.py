"""
Utility functions and decorators for enhanced logging functionality.
"""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, Optional, TypeVar, cast

from utils.logging_config import StructuredLogger, get_logger

# Type variable for generic function type
F = TypeVar('F', bound=Callable[..., Any])

def log_execution_time(logger: StructuredLogger) -> Callable[[F], F]:
    """
    Decorator to log function execution time.
    
    Args:
        logger: StructuredLogger instance to use for logging
    
    Usage:
        @log_execution_time(logger)
        def my_function():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(
                    f"Function {func.__name__} completed",
                    execution_time=execution_time,
                    status="success"
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Function {func.__name__} failed",
                    execution_time=execution_time,
                    error=str(e),
                    status="error"
                )
                raise
        return cast(F, wrapper)
    return decorator

@contextmanager
def log_operation(
    logger: StructuredLogger,
    operation: str,
    **context: Any
) -> Generator[None, None, None]:
    """
    Context manager to log the start and end of an operation with timing.
    
    Args:
        logger: StructuredLogger instance
        operation: Name of the operation being performed
        **context: Additional context to include in log messages
    
    Usage:
        with log_operation(logger, "data_processing", dataset="users"):
            process_data()
    """
    start_time = time.time()
    logger.info(f"Starting {operation}", operation_status="started", **context)
    
    try:
        yield
        execution_time = time.time() - start_time
        logger.info(
            f"Completed {operation}",
            operation_status="completed",
            execution_time=execution_time,
            **context
        )
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            f"Failed {operation}",
            operation_status="failed",
            execution_time=execution_time,
            error=str(e),
            **context
        )
        raise

def log_state_change(
    logger: StructuredLogger,
    state_name: str,
    old_state: Any,
    new_state: Any,
    **context: Any
) -> None:
    """
    Log a state transition with before/after values.
    
    Args:
        logger: StructuredLogger instance
        state_name: Name of the state being changed
        old_state: Previous state value
        new_state: New state value
        **context: Additional context to include
    """
    logger.info(
        f"State change: {state_name}",
        state_name=state_name,
        old_state=str(old_state),
        new_state=str(new_state),
        **context
    )

class ComponentLogger:
    """
    Base class for component-specific loggers with common logging patterns.
    """
    
    def __init__(self, component_name: str) -> None:
        self.logger = get_logger(component_name)
        self.component_name = component_name
        
    def log_startup(self, **context: Any) -> None:
        """Log component startup with configuration details."""
        self.logger.info(
            f"Starting {self.component_name}",
            event="startup",
            **context
        )
        
    def log_shutdown(self, **context: Any) -> None:
        """Log component shutdown with final state."""
        self.logger.info(
            f"Shutting down {self.component_name}",
            event="shutdown",
            **context
        )
        
    def log_health_check(self, status: str, **metrics: Any) -> None:
        """Log health check results with metrics."""
        self.logger.info(
            f"Health check: {status}",
            event="health_check",
            status=status,
            **metrics
        )
        
    def log_task_assignment(
        self,
        task_id: str,
        status: str,
        **context: Any
    ) -> None:
        """Log task assignment changes."""
        self.logger.info(
            f"Task assignment: {status}",
            event="task_assignment",
            task_id=task_id,
            status=status,
            **context
        )

# Common log contexts for different components
NODE_CONTEXT = {
    'component_type': 'node',
    'subsystem': 'core'
}

RENDERER_CONTEXT = {
    'component_type': 'renderer',
    'subsystem': 'content'
}

GOVERNOR_CONTEXT = {
    'component_type': 'governor',
    'subsystem': 'control'
}

HEALER_CONTEXT = {
    'component_type': 'healer',
    'subsystem': 'control'
}