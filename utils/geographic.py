"""
Geographic distribution utilities for Shortlist swarm.
Provides region detection, cross-region coordination, and geographic sharding capabilities.
"""

import json
import os
import socket
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from .logging_utils import ComponentLogger


class ConsistencyLevel(Enum):
    """Consistency requirements for different operation types."""
    EVENTUAL = "eventual"
    STRONG = "strong"
    REGIONAL = "regional"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    LAST_WRITER_WINS = "last_writer_wins"
    SEMANTIC_MERGE = "semantic_merge"
    REGION_PRIORITY = "region_priority"
    TIMESTAMP_PRIORITY = "timestamp_priority"


@dataclass
class RegionConfig:
    """Configuration for a geographic region."""
    name: str
    git_repo: Optional[str] = None
    priority: int = 5  # Lower = higher priority for coordinator election
    weight: int = 1    # Voting weight in quorum decisions
    timezone: str = "UTC"
    sync_interval_seconds: int = 300  # 5 minutes
    nodes: List[str] = None

    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []


@dataclass
class VectorClock:
    """Vector clock for tracking causality between regions."""
    clock: Dict[str, int]

    def __init__(self, regions: List[str]):
        self.clock = {region: 0 for region in regions}

    def increment(self, region: str) -> None:
        """Increment the clock for a specific region."""
        if region in self.clock:
            self.clock[region] += 1

    def update(self, other: 'VectorClock') -> None:
        """Update this clock with information from another clock."""
        for region in self.clock:
            if region in other.clock:
                self.clock[region] = max(self.clock[region], other.clock[region])

    def is_concurrent(self, other: 'VectorClock') -> bool:
        """Check if two vector clocks represent concurrent events."""
        self_greater = any(self.clock[r] > other.clock.get(r, 0) for r in self.clock)
        other_greater = any(other.clock.get(r, 0) > self.clock[r] for r in self.clock)
        return self_greater and other_greater

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for JSON serialization."""
        return self.clock.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'VectorClock':
        """Create from dictionary."""
        instance = cls([])
        instance.clock = data.copy()
        return instance


@dataclass
class OperationMetadata:
    """Metadata for cross-region operations."""
    operation_id: str
    region: str
    timestamp: str
    vector_clock: VectorClock
    consistency_level: ConsistencyLevel
    conflict_resolution: ConflictResolution

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'operation_id': self.operation_id,
            'region': self.region,
            'timestamp': self.timestamp,
            'vector_clock': self.vector_clock.to_dict(),
            'consistency_level': self.consistency_level.value,
            'conflict_resolution': self.conflict_resolution.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], regions: List[str]) -> 'OperationMetadata':
        """Create from dictionary."""
        return cls(
            operation_id=data['operation_id'],
            region=data['region'],
            timestamp=data['timestamp'],
            vector_clock=VectorClock.from_dict(data['vector_clock']),
            consistency_level=ConsistencyLevel(data['consistency_level']),
            conflict_resolution=ConflictResolution(data['conflict_resolution'])
        )


class GeographicManager:
    """Manages geographic distribution and cross-region coordination."""

    def __init__(self):
        from .logging_config import get_logger
        self.logger = get_logger("geographic_manager")
        self.config = self._load_config()
        self.current_region = self._detect_region()
        self.vector_clock = VectorClock(list(self.config.get('regions', {}).keys()))

        self.logger.info("Geographic manager initialized",
            current_region=self.current_region,
            available_regions=list(self.config.get('regions', {}).keys()),
            sharding_enabled=self.config.get('geographic_sharding', {}).get('enabled', False)
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load geographic configuration."""
        try:
            if os.path.exists('geographic_config.json'):
                with open('geographic_config.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning("Failed to load geographic config", error=str(e))

        # Default configuration for backward compatibility
        return {
            'geographic_sharding': {
                'enabled': False,
                'default_region': 'default'
            },
            'regions': {
                'default': {
                    'name': 'default',
                    'priority': 1,
                    'weight': 1,
                    'timezone': 'UTC'
                }
            },
            'consistency_policies': {
                'shortlist_updates': {
                    'consistency': 'eventual',
                    'max_lag_seconds': 30,
                    'conflict_resolution': 'semantic_merge'
                },
                'schedule_changes': {
                    'consistency': 'strong',
                    'quorum_required': True,
                    'timeout_seconds': 10
                },
                'node_roster': {
                    'consistency': 'eventual',
                    'max_lag_seconds': 60,
                    'conflict_resolution': 'last_writer_wins'
                }
            }
        }

    def _detect_region(self) -> str:
        """Detect the current region based on environment or configuration."""
        # Check environment variable first
        env_region = os.getenv('SHORTLIST_REGION')
        if env_region:
            return env_region

        # Try to detect from hostname or IP
        try:
            hostname = socket.gethostname()

            # Simple hostname-based detection (extend as needed)
            if any(marker in hostname.lower() for marker in ['eu', 'europe']):
                return 'eu-west'
            elif any(marker in hostname.lower() for marker in ['us', 'america']):
                return 'us-east'
            elif any(marker in hostname.lower() for marker in ['asia', 'apac']):
                return 'asia-pacific'

        except Exception as e:
            self.logger.warning("Region detection failed", error=str(e))

        # Fallback to default
        return self.config.get('geographic_sharding', {}).get('default_region', 'default')

    def is_sharding_enabled(self) -> bool:
        """Check if geographic sharding is enabled."""
        return self.config.get('geographic_sharding', {}).get('enabled', False)

    def get_region_config(self, region_name: str) -> Optional[RegionConfig]:
        """Get configuration for a specific region."""
        region_data = self.config.get('regions', {}).get(region_name)
        if not region_data:
            return None

        return RegionConfig(
            name=region_name,
            git_repo=region_data.get('git_repo'),
            priority=region_data.get('priority', 5),
            weight=region_data.get('weight', 1),
            timezone=region_data.get('timezone', 'UTC'),
            sync_interval_seconds=region_data.get('sync_interval_seconds', 300),
            nodes=region_data.get('nodes', [])
        )

    def get_current_region_config(self) -> RegionConfig:
        """Get configuration for the current region."""
        config = self.get_region_config(self.current_region)
        if config:
            return config

        # Fallback for unknown regions
        return RegionConfig(
            name=self.current_region,
            priority=10,  # Low priority for unknown regions
            weight=1
        )

    def get_all_regions(self) -> List[str]:
        """Get list of all configured regions."""
        return list(self.config.get('regions', {}).keys())

    def should_coordinate_globally(self, operation_type: str) -> bool:
        """Determine if an operation requires global coordination."""
        if not self.is_sharding_enabled():
            return False

        policy = self.config.get('consistency_policies', {}).get(operation_type, {})
        return policy.get('consistency') == 'strong' or policy.get('quorum_required', False)

    def get_consistency_policy(self, operation_type: str) -> Dict[str, Any]:
        """Get consistency policy for an operation type."""
        return self.config.get('consistency_policies', {}).get(operation_type, {
            'consistency': 'eventual',
            'max_lag_seconds': 60,
            'conflict_resolution': 'last_writer_wins'
        })

    def create_operation_metadata(self, operation_id: str, operation_type: str) -> OperationMetadata:
        """Create metadata for a cross-region operation."""
        policy = self.get_consistency_policy(operation_type)

        # Increment our vector clock
        self.vector_clock.increment(self.current_region)

        return OperationMetadata(
            operation_id=operation_id,
            region=self.current_region,
            timestamp=datetime.now(timezone.utc).isoformat(),
            vector_clock=self.vector_clock,
            consistency_level=ConsistencyLevel(policy.get('consistency', 'eventual')),
            conflict_resolution=ConflictResolution(policy.get('conflict_resolution', 'last_writer_wins'))
        )

    def is_regional_task(self, task_config: Dict[str, Any]) -> bool:
        """Check if a task is region-specific."""
        return 'required_region' in task_config or 'regional_ownership' in task_config

    def can_execute_task(self, task_config: Dict[str, Any]) -> bool:
        """Check if current region can execute a task."""
        # Check required region
        required_region = task_config.get('required_region')
        if required_region and required_region != self.current_region:
            return False

        # Check regional ownership
        regional_ownership = self.config.get('regional_ownership', {})
        task_id = task_config.get('id', '')

        for region, owned_tasks in regional_ownership.items():
            if any(pattern in task_id for pattern in owned_tasks):
                return region == self.current_region

        # If no specific requirements, any region can execute
        return True

    def add_regional_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add regional context to data structures."""
        if not self.is_sharding_enabled():
            return data

        # Add region to node entries
        if 'nodes' in data:
            for node in data['nodes']:
                if 'region' not in node:
                    node['region'] = self.current_region

        # Add regional metadata
        if 'regional_metadata' not in data:
            data['regional_metadata'] = {
                'region': self.current_region,
                'vector_clock': self.vector_clock.to_dict(),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }

        return data

    def needs_cross_region_sync(self, operation_type: str, last_sync: Optional[datetime] = None) -> bool:
        """Determine if cross-region sync is needed."""
        if not self.is_sharding_enabled():
            return False

        if last_sync is None:
            return True

        policy = self.get_consistency_policy(operation_type)
        max_lag = timedelta(seconds=policy.get('max_lag_seconds', 60))

        return datetime.now(timezone.utc) - last_sync > max_lag


# Global instance
_geographic_manager = None

def get_geographic_manager() -> GeographicManager:
    """Get the global geographic manager instance."""
    global _geographic_manager
    if _geographic_manager is None:
        _geographic_manager = GeographicManager()
    return _geographic_manager