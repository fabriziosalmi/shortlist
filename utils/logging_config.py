"""
Structured logging configuration for the Shortlist system.
Provides consistent logging setup across all components with JSON formatting
and contextual information.
"""

import json
import logging
import logging.config
import socket
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

# Custom JSON formatter for structured logging
class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format with additional context."""
    
    def __init__(self) -> None:
        super().__init__()
        self.hostname = socket.gethostname()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string with standardized fields."""
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', 
                                time.gmtime(record.created))
        
        # Base log entry with standard fields
        log_entry = {
            "timestamp": timestamp,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "hostname": self.hostname,
            "thread": threading.current_thread().name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add extra fields from the record
        if hasattr(record, 'extras'):
            log_entry.update(record.extras)

        # Include formatted exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry)

def configure_logging(
    component_name: str,
    log_level: str = "INFO",
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging for a component with JSON formatting and optional file output.

    Args:
        component_name: Name of the component (e.g., 'node', 'web_renderer')
        log_level: Logging level (default: "INFO")
        log_file: Optional path to log file. If None, logs to stdout only.
    """
    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'stream': sys.stdout
        }
    }

    if log_file:
        handlers['file'] = {
            'class': 'logging.FileHandler',
            'formatter': 'json',
            'filename': log_file
        }

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': JsonFormatter
            }
        },
        'handlers': handlers,
        'loggers': {
            component_name: {
                'handlers': list(handlers.keys()),
                'level': log_level,
                'propagate': False
            }
        }
    })

class StructuredLogger:
    """
    Enhanced logger that supports structured logging with context.
    """
    
    def __init__(self, name: str) -> None:
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def add_context(self, **kwargs: Any) -> None:
        """Add persistent context to all subsequent log messages."""
        self.context.update(kwargs)

    def remove_context(self, *keys: str) -> None:
        """Remove specified keys from the logging context."""
        for key in keys:
            self.context.pop(key, None)

    def _log(self, level: int, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        """Internal method to handle structured logging with context."""
        extras = self.context.copy()
        if extra:
            extras.update(extra)
        if kwargs:
            extras.update(kwargs)
        
        self.logger.log(level, msg, extra={'extras': extras})

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, **kwargs)

    @contextmanager
    def context_bind(self, **kwargs: Any) -> Generator[None, None, None]:
        """
        Temporarily bind additional context to the logger.
        
        Usage:
            with logger.context_bind(task_id='123'):
                logger.info('Processing task')
        """
        temp_context = kwargs
        self.add_context(**temp_context)
        try:
            yield
        finally:
            for key in temp_context:
                self.remove_context(key)

def get_logger(component_name: str) -> StructuredLogger:
    """
    Get a configured structured logger for a component.
    
    Args:
        component_name: Name of the component requesting the logger
        
    Returns:
        StructuredLogger: Configured logger instance
    """
    return StructuredLogger(component_name)