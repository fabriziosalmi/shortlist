"""
Configuration management for Shortlist nodes.

This module handles dynamic loading and application of swarm-wide configuration,
allowing for centralized control of node behavior through swarm_config.json.
"""

import json
import os
import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from copy import deepcopy

logger = logging.getLogger(__name__)

@dataclass
class IntervalConfig:
    """Timing intervals for various operations."""
    node_heartbeat_seconds: int = 300
    task_heartbeat_seconds: int = 60
    idle_loop_seconds: int = 15
    git_sync_seconds: int = 10
    renderer_health_check_seconds: int = 20

@dataclass
class TimeoutConfig:
    """Timeout values for various operations."""
    node_timeout_seconds: int = 900
    task_timeout_seconds: int = 180
    git_operation_seconds: int = 30
    renderer_startup_seconds: int = 60
    renderer_health_check_seconds: int = 10

@dataclass
class JitterConfig:
    """Configuration for timing jitter to prevent swarm synchronization."""
    min_seconds: int = 1
    max_seconds: int = 8

@dataclass
class ResilienceConfig:
    """Configuration for error handling and retry behavior."""
    max_git_retries: int = 3
    git_retry_delay_seconds: int = 5
    max_renderer_restarts: int = 2
    renderer_restart_delay_seconds: int = 30

@dataclass
class MemoryConfig:
    """Memory management configuration."""
    max_renderer_memory_mb: int = 512
    memory_warning_threshold_percent: int = 80

@dataclass
class FeatureFlags:
    """Toggle flags for experimental or optional features."""
    enable_task_preemption: bool = False
    enable_auto_scaling: bool = False
    strict_health_checks: bool = True

@dataclass
class SwarmConfig:
    """Central configuration for Shortlist node behavior."""
    log_level: str = "INFO"
    intervals: IntervalConfig = field(default_factory=IntervalConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    jitter: JitterConfig = field(default_factory=JitterConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    memory_limits: MemoryConfig = field(default_factory=MemoryConfig)
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)

    @property
    def node_heartbeat_interval(self) -> timedelta:
        return timedelta(seconds=self.intervals.node_heartbeat_seconds)

    @property
    def task_heartbeat_interval(self) -> timedelta:
        return timedelta(seconds=self.intervals.task_heartbeat_seconds)

    @property
    def node_timeout(self) -> timedelta:
        return timedelta(seconds=self.timeouts.node_timeout_seconds)

    @property
    def task_timeout(self) -> timedelta:
        return timedelta(seconds=self.timeouts.task_timeout_seconds)

class ConfigurationManager:
    """Manages loading and applying swarm configuration."""
    
    def __init__(self, config_path: str = "swarm_config.json"):
        self.config_path = config_path
        self._current_config = SwarmConfig()
        self._last_loaded_data: Dict[str, Any] = {}
    
    def load_and_validate(self) -> SwarmConfig:
        """Load configuration from file and validate it.
        
        Returns:
            SwarmConfig: Current configuration (default if load fails)
        """
        try:
            # Start with a fresh copy of current config
            config_data = self._read_config_file()
            if not config_data:
                return deepcopy(self._current_config)
            
            # Track changes for logging
            changes = []
            
            # Update each section that exists in the file
            new_config = deepcopy(self._current_config)
            
            # Handle top-level fields
            if 'log_level' in config_data:
                old_level = new_config.log_level
                new_config.log_level = config_data['log_level']
                if old_level != new_config.log_level:
                    changes.append(f"log_level: {old_level} → {new_config.log_level}")
            
            # Handle nested configuration objects
            for section in ['intervals', 'timeouts', 'jitter', 'resilience', 
                          'memory_limits', 'feature_flags']:
                if section in config_data:
                    current_section = getattr(new_config, section)
                    new_values = config_data[section]
                    
                    for key, value in new_values.items():
                        if hasattr(current_section, key):
                            old_value = getattr(current_section, key)
                            setattr(current_section, key, value)
                            if old_value != value:
                                changes.append(f"{section}.{key}: {old_value} → {value}")
            
            # Log changes if any were detected
            if changes:
                logger.info("Remote configuration changes detected:\n• " + 
                          "\n• ".join(changes))
            
            self._current_config = new_config
            self._last_loaded_data = config_data
            
            return new_config
            
        except Exception as e:
            logger.error(f"Failed to load remote configuration: {e}",
                        exc_info=True)
            return deepcopy(self._current_config)
    
    def _read_config_file(self) -> Optional[Dict[str, Any]]:
        """Read and parse the configuration file."""
        try:
            if not os.path.exists(self.config_path):
                logger.debug(f"Configuration file not found: {self.config_path}")
                return None
            
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            # Remove comment field if present
            data.pop('comment', None)
            return data
            
        except Exception as e:
            logger.error(f"Error reading configuration file: {e}",
                        exc_info=True)
            return None
    
    def apply_log_level(self) -> None:
        """Apply the current log level configuration."""
        try:
            level = getattr(logging, self._current_config.log_level.upper())
            logging.getLogger().setLevel(level)
            logger.info(f"Set log level to {self._current_config.log_level}")
        except (AttributeError, TypeError):
            logger.error(f"Invalid log level: {self._current_config.log_level}")
    
    @property
    def current(self) -> SwarmConfig:
        """Get the current configuration."""
        return deepcopy(self._current_config)