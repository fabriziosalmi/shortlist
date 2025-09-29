"""
Task sharding management for Shortlist.

This module handles splitting large tasks into parallel shards
and managing their execution and recombination.
"""

import math
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ShardConfig:
    """Configuration for task sharding."""
    enabled: bool = False
    items_per_shard: int = 10
    min_items_for_sharding: int = 20  # Don't shard if fewer items
    max_shards: int = 10  # Limit total number of shards

@dataclass
class ShardInfo:
    """Information about a specific shard."""
    shard_id: str
    total_shards: int
    start_index: int
    end_index: int
    parent_task: Dict[str, Any]

def calculate_optimal_shards(
    total_items: int,
    config: ShardConfig
) -> int:
    """Calculate the optimal number of shards.
    
    Args:
        total_items: Total number of items to process
        config: Sharding configuration
    
    Returns:
        Number of shards to create
    """
    if total_items < config.min_items_for_sharding:
        return 1
    
    # Calculate based on items_per_shard
    desired_shards = math.ceil(total_items / config.items_per_shard)
    
    # Limit to max_shards
    return min(desired_shards, config.max_shards)

def create_shard_task(
    parent_task: Dict[str, Any],
    shard_info: ShardInfo
) -> Dict[str, Any]:
    """Create a task definition for a shard.
    
    Args:
        parent_task: Original task being sharded
        shard_info: Information about this shard
    
    Returns:
        Task definition for the shard
    """
    task_type = parent_task["type"]
    
    return {
        "id": f"{parent_task['id']}_shard_{shard_info.shard_id}",
        "type": f"{task_type}_shard",
        "priority": parent_task.get("priority", 0),
        "required_role": parent_task.get("required_role"),
        "config": {
            **parent_task.get("config", {}),
            "shard": {
                "id": shard_info.shard_id,
                "total_shards": shard_info.total_shards,
                "start_index": shard_info.start_index,
                "end_index": shard_info.end_index,
                "parent_task_id": parent_task["id"]
            }
        }
    }

def create_combiner_task(
    parent_task: Dict[str, Any],
    total_shards: int
) -> Dict[str, Any]:
    """Create a task definition for the combiner.
    
    Args:
        parent_task: Original task being sharded
        total_shards: Total number of shards
    
    Returns:
        Task definition for the combiner
    """
    task_type = parent_task["type"]
    
    return {
        "id": f"{parent_task['id']}_combiner",
        "type": f"{task_type}_combiner",
        "priority": parent_task.get("priority", 0),
        "required_role": parent_task.get("required_role"),
        "config": {
            **parent_task.get("config", {}),
            "combine": {
                "parent_task_id": parent_task["id"],
                "total_shards": total_shards,
                "shard_task_pattern": f"{parent_task['id']}_shard_*"
            }
        }
    }

def get_shard_tasks(
    task: Dict[str, Any],
    total_items: int,
    config: Optional[ShardConfig] = None
) -> List[Dict[str, Any]]:
    """Get all shard tasks for a given task.
    
    Args:
        task: Original task to shard
        total_items: Total number of items to process
        config: Optional sharding configuration
    
    Returns:
        List of shard task definitions
    """
    if config is None:
        config = ShardConfig()
    
    # Parse task's sharding config
    task_config = task.get("sharding", {})
    if isinstance(task_config, bool):
        task_config = {"enabled": task_config}
    
    # Merge with default config
    effective_config = ShardConfig(
        enabled=task_config.get("enabled", config.enabled),
        items_per_shard=task_config.get("items_per_shard", config.items_per_shard),
        min_items_for_sharding=task_config.get("min_items_for_sharding", config.min_items_for_sharding),
        max_shards=task_config.get("max_shards", config.max_shards)
    )
    
    # Check if sharding is needed
    if not effective_config.enabled:
        return []
    
    num_shards = calculate_optimal_shards(total_items, effective_config)
    if num_shards <= 1:
        return []
    
    # Calculate shard boundaries
    items_per_shard = math.ceil(total_items / num_shards)
    shard_tasks = []
    
    # Create shard tasks
    for i in range(num_shards):
        start_idx = i * items_per_shard
        end_idx = min(start_idx + items_per_shard, total_items)
        
        shard_info = ShardInfo(
            shard_id=str(i + 1),
            total_shards=num_shards,
            start_index=start_idx,
            end_index=end_idx,
            parent_task=task
        )
        
        shard_task = create_shard_task(task, shard_info)
        shard_tasks.append(shard_task)
    
    # Add combiner task
    combiner_task = create_combiner_task(task, num_shards)
    shard_tasks.append(combiner_task)
    
    return shard_tasks

def get_shard_item_slice(
    items: List[Any],
    shard_config: Dict[str, Any]
) -> List[Any]:
    """Get the items for a specific shard.
    
    Args:
        items: Full list of items
        shard_config: Shard configuration from task
    
    Returns:
        List of items for this shard
    """
    start = shard_config["start_index"]
    end = shard_config["end_index"]
    return items[start:end]

def is_shard_task(task: Dict[str, Any]) -> bool:
    """Check if a task is a shard task.
    
    Args:
        task: Task to check
    
    Returns:
        True if task is a shard
    """
    return task.get("type", "").endswith("_shard")

def is_combiner_task(task: Dict[str, Any]) -> bool:
    """Check if a task is a combiner task.
    
    Args:
        task: Task to check
    
    Returns:
        True if task is a combiner
    """
    return task.get("type", "").endswith("_combiner")