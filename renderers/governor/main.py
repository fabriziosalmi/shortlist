import os
import time
import json
import subprocess
from datetime import datetime, timedelta
from dateutil.parser import parse as date_parse
import requests
from typing import Dict, List, Any, Optional, Tuple

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    GOVERNOR_CONTEXT,
    log_operation,
    log_execution_time
)

# --- Configuration ---
GIT_REPO_PATH = "."  # Current directory
GOVERNOR_LOOP_INTERVAL_SECONDS = 60
SWARM_METRIC_AGG_TIMEOUT_MINUTES = 15 # How recent a node's heartbeat must be to be considered "alive"

# Quorum configuration
DEFAULT_MIN_NODES_ALIVE = 1  # Don't require quorum by default
DEFAULT_MIN_PERCENT_ALIVE = 0  # Don't require quorum by default

# Configure logging
configure_logging('governor_renderer', log_level="INFO", log_file='/app/data/governor.log')
logger = ComponentLogger('governor_renderer')
logger.logger.add_context(**GOVERNOR_CONTEXT)

# --- Git Utilities ---
@log_execution_time(logger.logger)
def git_pull_rebase() -> None:
    """Perform git pull with rebase."""
    with log_operation(logger.logger, "git_pull_rebase"):
        try:
            result = subprocess.run(["git", "pull", "--rebase"], cwd=GIT_REPO_PATH, capture_output=True, text=True, check=True)
            logger.logger.info("Git pull successful", output=result.stdout.strip())
        except subprocess.CalledProcessError as e:
            logger.logger.error("Git pull failed",
                              error=e.stderr.strip(),
                              error_type=type(e).__name__)
            raise
        except Exception as e:
            logger.logger.error("Unexpected error during git pull",
                              error=str(e),
                              error_type=type(e).__name__)
            raise

@log_execution_time(logger.logger)
def git_commit_push(message: str) -> None:
    """Commit and push changes to git repository.
    
    Args:
        message: Commit message
    """
    with log_operation(logger.logger, "git_commit_push", commit_message=message):
        try:
            subprocess.run(["git", "add", "schedule.json"], cwd=GIT_REPO_PATH, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=GIT_REPO_PATH, check=True)
            result = subprocess.run(["git", "push"], cwd=GIT_REPO_PATH, capture_output=True, text=True, check=True)
            logger.logger.info("Git commit and push successful",
                             output=result.stdout.strip())
        except subprocess.CalledProcessError as e:
            logger.logger.error("Git commit/push failed",
                              error=e.stderr.strip(),
                              error_type=type(e).__name__)
            raise
        except Exception as e:
            logger.logger.error("Unexpected error during git commit/push",
                              error=str(e),
                              error_type=type(e).__name__)
            raise

# --- JSON File Handling ---
@log_execution_time(logger.logger)
def read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dict containing the parsed JSON data, or None on error
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.logger.warning("File not found", filepath=file_path)
        return None
    except json.JSONDecodeError as e:
        logger.logger.error("Failed to decode JSON",
                          error=str(e),
                          error_type=type(e).__name__,
                          filepath=file_path)
        return None
    except Exception as e:
        logger.logger.error("Failed to read file",
                          error=str(e),
                          error_type=type(e).__name__,
                          filepath=file_path)
        return None

@log_execution_time(logger.logger)
def write_json_file(file_path: str, data: Dict[str, Any]) -> None:
    """Write data to a JSON file.
    
    Args:
        file_path: Path to the JSON file
        data: Data to write to the file
    """
    with log_operation(logger.logger, "write_json", filepath=file_path):
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.logger.info("Successfully wrote JSON file")
        except Exception as e:
            logger.logger.error("Failed to write JSON file",
                              error=str(e),
                              error_type=type(e).__name__)
            raise

# --- Quorum Logic ---
@log_execution_time(logger.logger)
def calculate_swarm_health(roster: Dict[str, Any]) -> Tuple[int, int]:
    """Calculate current swarm health metrics.
    
    Args:
        roster: The roster data dictionary
        
    Returns:
        Tuple containing:
        - Number of nodes in roster
        - Number of alive nodes
    """
    total_nodes = len(roster.get("nodes", []))
    alive_nodes = 0
    now = datetime.utcnow()
    
    for node_data in roster.get("nodes", []):
        last_seen_str = node_data.get("last_seen")
        if last_seen_str:
            last_seen = date_parse(last_seen_str)
            if now - last_seen < timedelta(minutes=SWARM_METRIC_AGG_TIMEOUT_MINUTES):
                alive_nodes += 1
    
    logger.logger.info("Calculated swarm health",
                    total_nodes=total_nodes,
                    alive_nodes=alive_nodes,
                    alive_percentage=round(alive_nodes / total_nodes * 100 if total_nodes > 0 else 0, 1))
    
    return total_nodes, alive_nodes

@log_execution_time(logger.logger)
def check_quorum(trigger_data: Dict[str, Any], total_nodes: int, alive_nodes: int) -> bool:
    """Check if quorum requirements are met for a trigger.
    
    Args:
        trigger_data: Trigger configuration dictionary
        total_nodes: Total number of nodes in roster
        alive_nodes: Number of currently alive nodes
        
    Returns:
        bool: True if quorum is met or not required, False otherwise
    """
    quorum = trigger_data.get("quorum", {})
    if not quorum:
        return True  # No quorum required
    
    min_nodes = quorum.get("min_nodes_alive", DEFAULT_MIN_NODES_ALIVE)
    min_percent = quorum.get("min_percent_alive", DEFAULT_MIN_PERCENT_ALIVE)
    
    # Calculate current percentage of alive nodes
    alive_percent = (alive_nodes / total_nodes * 100) if total_nodes > 0 else 0
    
    nodes_ok = alive_nodes >= min_nodes
    percent_ok = alive_percent >= min_percent
    
    quorum_met = nodes_ok and percent_ok
    
    if not quorum_met:
        logger.logger.warning("Quorum not met",
                          trigger_id=trigger_data.get("id"),
                          alive_nodes=alive_nodes,
                          min_nodes=min_nodes,
                          alive_percent=round(alive_percent, 1),
                          min_percent=min_percent)
    else:
        logger.logger.debug("Quorum met",
                         trigger_id=trigger_data.get("id"),
                         alive_nodes=alive_nodes,
                         alive_percent=round(alive_percent, 1))
    
    return quorum_met

# --- Trigger Processing Logic ---
def evaluate_condition_time_based(condition):
    now_utc = datetime.utcnow()
    start_time_str = condition.get("start_utc")
    end_time_str = condition.get("end_utc")

    if start_time_str:
        start_time = date_parse(start_time_str)
        if now_utc < start_time:
            return False
    if end_time_str:
        end_time = date_parse(end_time_str)
        if now_utc > end_time:
            return False
    return True

def evaluate_condition_swarm_metric_agg(condition, roster):
    metric_name = condition.get("metric")
    aggregation_type = condition.get("aggregation") # e.g., "average", "sum", "count_above_threshold"
    threshold = condition.get("threshold")
    operator = condition.get("operator") # e.g., "gt", "lt", "eq"

    if not all([metric_name, aggregation_type, threshold, operator]):
            logger.logger.warning("Incomplete metric aggregation condition",
                               metric=metric_name,
                               aggregation=aggregation_type,
                               threshold=threshold,
                               operator=operator)
        return False

    alive_nodes_metrics = []
    now = datetime.utcnow()
    for node_id, node_data in roster.get("nodes", {}).items():
        last_seen_str = node_data.get("last_seen")
        if last_seen_str:
            last_seen = date_parse(last_seen_str)
            if now - last_seen < timedelta(minutes=SWARM_METRIC_AGG_TIMEOUT_MINUTES):
                metric_value = node_data.get("metrics", {}).get(metric_name)
                if metric_value is not None:
                    alive_nodes_metrics.append(metric_value)

    if not alive_nodes_metrics:
            logger.logger.info("No alive nodes with metric",
                             metric_name=metric_name)
        return False

    aggregated_value = None
    if aggregation_type == "average":
        aggregated_value = sum(alive_nodes_metrics) / len(alive_nodes_metrics)
    elif aggregation_type == "sum":
        aggregated_value = sum(alive_nodes_metrics)
    elif aggregation_type == "count_above_threshold":
        count = 0
        for val in alive_nodes_metrics:
            if eval(f"{val} {operator_to_symbol(operator)} {threshold}"): # Dangerous, but for simplicity
                count += 1
        aggregated_value = count
    # Add other aggregation types as needed

    if aggregated_value is None:
            logger.logger.warning("Unsupported aggregation type",
                               aggregation_type=aggregation_type)
        return False

    # Evaluate against threshold
    if operator == "gt":
        return aggregated_value > threshold
    elif operator == "lt":
        return aggregated_value < threshold
    elif operator == "eq":
        return aggregated_value == threshold
    # Add other operators as needed
    logger.logger.warning("Unsupported operator", operator=operator)
    return False

def operator_to_symbol(op):
    if op == "gt": return ">"
    if op == "lt": return "<"
    if op == "eq": return "=="
    return "" # Should not happen with proper validation

def apply_action(action, current_schedule):
    action_type = action.get("type")
    task_id = action.get("task_id")
    task_type = action.get("task_type")
    priority = action.get("priority")
    swap_with_task_id = action.get("swap_with_task_id")

    if action_type == "ADD_TASK":
        if not any(t.get("id") == task_id for t in current_schedule.get("tasks", [])):
            current_schedule.setdefault("tasks", []).append({"id": task_id, "type": task_type, "priority": priority})
            logger.logger.info("Added task",
                             task_id=task_id,
                             task_type=task_type,
                             priority=priority)
            return True
    elif action_type == "REMOVE_TASK":
        original_len = len(current_schedule.get("tasks", []))
        current_schedule["tasks"] = [t for t in current_schedule.get("tasks", []) if t.get("id") != task_id]
        if len(current_schedule["tasks"]) < original_len:
            logger.logger.info("Removed task", task_id=task_id)
            return True
    elif action_type == "SWAP_TASKS":
        if task_id and swap_with_task_id:
            idx1, idx2 = -1, -1
            for i, task in enumerate(current_schedule.get("tasks", [])):
                if task.get("id") == task_id:
                    idx1 = i
                if task.get("id") == swap_with_task_id:
                    idx2 = i
            if idx1 != -1 and idx2 != -1:
                current_schedule["tasks"][idx1], current_schedule["tasks"][idx2] = current_schedule["tasks"][idx2], current_schedule["tasks"][idx1]
                logger.logger.info("Swapped tasks",
                                 task_id_1=task_id,
                                 task_id_2=swap_with_task_id)
                return True
    return False # No change or unsupported action

def main() -> None:
    """Main loop for the governor renderer."""
    logger.log_startup()
    
    while True:
        with log_operation(logger.logger, "governor_cycle"):
            try:
                git_pull_rebase()

            roster = read_json_file("roster.json")
            schedule = read_json_file("schedule.json")
            triggers = read_json_file("triggers.json")

        if not all([roster, schedule, triggers]):
            logger.logger.error("Failed to read required files",
                             roster_exists=bool(roster),
                             schedule_exists=bool(schedule),
                             triggers_exists=bool(triggers))
            time.sleep(GOVERNOR_LOOP_INTERVAL_SECONDS)
            continue
        
        # Calculate current swarm health
        total_nodes, alive_nodes = calculate_swarm_health(roster)
        
        original_schedule_str = json.dumps(schedule, indent=2)
        modified_schedule = json.loads(original_schedule_str) # Deep copy
        
        schedule_changed = False
        
        for trigger_id, trigger_data in triggers.get("triggers", {}).items():
            # Check quorum requirements first
            if not check_quorum(trigger_data, total_nodes, alive_nodes):
                continue  # Skip trigger if quorum not met
                condition_met = False
                condition_type = trigger_data.get("condition", {}).get("type")

                if condition_type == "time_based":
                    condition_met = evaluate_condition_time_based(trigger_data["condition"])
                elif condition_type == "swarm_metric_agg":
                    condition_met = evaluate_condition_swarm_metric_agg(trigger_data["condition"], roster)
                # Add other condition types as needed

                if condition_met:
                    logger.logger.info("Trigger condition met",
                                      trigger_id=trigger_id,
                                      condition_type=condition_type)
                    for action in trigger_data.get("actions", []):
                        if apply_action(action, modified_schedule):
                            schedule_changed = True
                else:
                    logger.logger.debug("Trigger condition not met",
                                      trigger_id=trigger_id,
                                      condition_type=condition_type)

            if schedule_changed:
                logger.logger.info("Schedule modified",
                                 tasks_count=len(modified_schedule.get("tasks", [])))
                write_json_file("schedule.json", modified_schedule)
                git_commit_push(f"chore(governor): Applied schedule changes via triggers")
            else:
                logger.logger.info("No schedule changes")

        except Exception as e:
            logger.logger.error("Error in governor cycle",
                              error=str(e),
                              error_type=type(e).__name__,
                              exc_info=True)

        time.sleep(GOVERNOR_LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
