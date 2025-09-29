"""
Chaos-enabled mock Git manager for Shortlist simulation.

This module extends the MockGitManager to inject failures, latency,
and other chaos conditions for testing system resilience.
"""

import time
import random
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

@dataclass
class ChaosConfig:
    """Configuration for chaos conditions."""
    
    # Latency settings (in seconds)
    min_latency: float = 0.1
    max_latency: float = 2.0
    latency_distribution: str = "uniform"  # or "exponential"
    
    # Failure rates (0-1)
    read_failure_rate: float = 0.05
    write_failure_rate: float = 0.1
    sync_failure_rate: float = 0.15
    push_failure_rate: float = 0.2
    
    # Network partition simulation
    partition_probability: float = 0.01  # Chance to enter partition mode
    partition_duration: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    
    # Rate limiting
    max_operations_per_minute: int = 120

@dataclass
class OperationMetrics:
    """Tracks operation metrics."""
    total_operations: int = 0
    failed_operations: int = 0
    total_latency: float = 0.0
    
    def record_operation(self, success: bool, latency: float) -> None:
        """Record a single operation."""
        self.total_operations += 1
        if not success:
            self.failed_operations += 1
        self.total_latency += latency

@dataclass
class GitMetrics:
    """Collects Git operation metrics."""
    reads: OperationMetrics = field(default_factory=OperationMetrics)
    writes: OperationMetrics = field(default_factory=OperationMetrics)
    syncs: OperationMetrics = field(default_factory=OperationMetrics)
    pushes: OperationMetrics = field(default_factory=OperationMetrics)

class ChaosGitManager:
    """Git manager that simulates real-world chaos conditions."""
    
    def __init__(
        self,
        config: Optional[ChaosConfig] = None,
        initial_state: Optional[Dict[str, Any]] = None
    ):
        """Initialize the chaos Git manager.
        
        Args:
            config: Chaos configuration
            initial_state: Initial repository state
        """
        self.config = config or ChaosConfig()
        self.state = initial_state or {}
        self.remote_state = self.state.copy()
        self.metrics = GitMetrics()
        
        # Track operation timing
        self.operation_times: List[float] = []
        self.operation_lock = Lock()
        
        # Network partition simulation
        self.partition_until: Optional[datetime] = None
    
    def _should_fail(self, failure_rate: float) -> bool:
        """Determine if an operation should fail."""
        return random.random() < failure_rate
    
    def _get_latency(self) -> float:
        """Get simulated network latency."""
        if self.config.latency_distribution == "exponential":
            # Use exponential distribution for more realistic network latency
            mean_latency = (self.config.min_latency + self.config.max_latency) / 2
            return random.expovariate(1.0 / mean_latency)
        else:
            # Uniform distribution
            return random.uniform(self.config.min_latency, self.config.max_latency)
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        
        with self.operation_lock:
            # Remove old operations
            cutoff = now - 60  # 1 minute window
            self.operation_times = [t for t in self.operation_times if t > cutoff]
            
            # Check if we're at limit
            if len(self.operation_times) >= self.config.max_operations_per_minute:
                return False
            
            # Record new operation
            self.operation_times.append(now)
            return True
    
    def _check_partition(self) -> None:
        """Check and potentially enter network partition mode."""
        now = datetime.now()
        
        # Check if we should enter partition
        if not self.partition_until and random.random() < self.config.partition_probability:
            self.partition_until = now + self.config.partition_duration
            logger.warning("Entering network partition",
                         duration=str(self.config.partition_duration))
        
        # Check if we're in partition
        if self.partition_until and now < self.partition_until:
            raise ConnectionError("Network partition simulated")
        elif self.partition_until and now >= self.partition_until:
            self.partition_until = None
            logger.info("Network partition ended")
    
    def read_json(self, file_path: str) -> Dict[str, Any]:
        """Read a JSON file from the mock repository."""
        start_time = time.time()
        success = True
        
        try:
            self._check_partition()
            if not self._check_rate_limit():
                raise ConnectionError("Rate limit exceeded")
            
            # Simulate read failures
            if self._should_fail(self.config.read_failure_rate):
                raise ConnectionError("Simulated read failure")
            
            # Simulate latency
            time.sleep(self._get_latency())
            
            # Actual read
            content = self.state.get(file_path, {})
            return content.copy()
            
        except Exception as e:
            success = False
            raise
        
        finally:
            latency = time.time() - start_time
            self.metrics.reads.record_operation(success, latency)
    
    def write_json(self, file_path: str, content: Dict[str, Any]) -> None:
        """Write a JSON file to the mock repository."""
        start_time = time.time()
        success = True
        
        try:
            self._check_partition()
            if not self._check_rate_limit():
                raise ConnectionError("Rate limit exceeded")
            
            # Simulate write failures
            if self._should_fail(self.config.write_failure_rate):
                raise ConnectionError("Simulated write failure")
            
            # Simulate latency
            time.sleep(self._get_latency())
            
            # Actual write
            self.state[file_path] = content.copy()
            
        except Exception as e:
            success = False
            raise
        
        finally:
            latency = time.time() - start_time
            self.metrics.writes.record_operation(success, latency)
    
    def sync(self) -> bool:
        """Sync with remote state."""
        start_time = time.time()
        success = True
        
        try:
            self._check_partition()
            if not self._check_rate_limit():
                raise ConnectionError("Rate limit exceeded")
            
            # Simulate sync failures
            if self._should_fail(self.config.sync_failure_rate):
                raise ConnectionError("Simulated sync failure")
            
            # Simulate latency
            time.sleep(self._get_latency())
            
            # Actual sync
            self.state = self.remote_state.copy()
            return True
            
        except Exception as e:
            success = False
            return False
        
        finally:
            latency = time.time() - start_time
            self.metrics.syncs.record_operation(success, latency)
    
    def commit_and_push(self, files: List[str], message: str) -> bool:
        """Commit and push changes to remote."""
        start_time = time.time()
        success = True
        
        try:
            self._check_partition()
            if not self._check_rate_limit():
                raise ConnectionError("Rate limit exceeded")
            
            # Simulate push failures
            if self._should_fail(self.config.push_failure_rate):
                raise ConnectionError("Simulated push failure")
            
            # Simulate latency
            time.sleep(self._get_latency())
            
            # Actual push
            updates = {
                file_path: self.state[file_path]
                for file_path in files
                if file_path in self.state
            }
            self.remote_state.update(updates)
            return True
            
        except Exception as e:
            success = False
            return False
        
        finally:
            latency = time.time() - start_time
            self.metrics.pushes.record_operation(success, latency)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get operation metrics."""
        metrics = {
            "operations": {
                "reads": {
                    "total": self.metrics.reads.total_operations,
                    "failed": self.metrics.reads.failed_operations,
                    "avg_latency": (
                        self.metrics.reads.total_latency / 
                        max(1, self.metrics.reads.total_operations)
                    )
                },
                "writes": {
                    "total": self.metrics.writes.total_operations,
                    "failed": self.metrics.writes.failed_operations,
                    "avg_latency": (
                        self.metrics.writes.total_latency /
                        max(1, self.metrics.writes.total_operations)
                    )
                },
                "syncs": {
                    "total": self.metrics.syncs.total_operations,
                    "failed": self.metrics.syncs.failed_operations,
                    "avg_latency": (
                        self.metrics.syncs.total_latency /
                        max(1, self.metrics.syncs.total_operations)
                    )
                },
                "pushes": {
                    "total": self.metrics.pushes.total_operations,
                    "failed": self.metrics.pushes.failed_operations,
                    "avg_latency": (
                        self.metrics.pushes.total_latency /
                        max(1, self.metrics.pushes.total_operations)
                    )
                }
            },
            "current_partition": bool(self.partition_until),
            "rate_limiting": {
                "operations_last_minute": len(self.operation_times),
                "max_operations_per_minute": self.config.max_operations_per_minute
            }
        }
        
        return metrics