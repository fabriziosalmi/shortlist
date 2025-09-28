import os
import time
import json
import logging
import subprocess
from datetime import datetime, timedelta
from dateutil.parser import parse as date_parse
import requests

# --- Configuration ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

GIT_REPO_PATH = "." # Current directory
GOVERNOR_LOOP_INTERVAL_SECONDS = 60
SWARM_METRIC_AGG_TIMEOUT_MINUTES = 15 # How recent a node's heartbeat must be to be considered "alive"

# --- Git Utilities ---
def git_pull_rebase():
    logging.info("Performing git pull --rebase...")
    try:
        result = subprocess.run(["git", "pull", "--rebase"], cwd=GIT_REPO_PATH, capture_output=True, text=True, check=True)
        logging.info(f"Git pull --rebase successful: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Git pull --rebase failed: {e.stderr.strip()}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred during git pull --rebase: {e}")
        raise

def git_commit_push(message):
    logging.info(f"Committing and pushing changes with message: '{message}'")
    try:
        subprocess.run(["git", "add", "schedule.json"], cwd=GIT_REPO_PATH, check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=GIT_REPO_PATH, check=True)
        result = subprocess.run(["git", "push"], cwd=GIT_REPO_PATH, capture_output=True, text=True, check=True)
        logging.info(f"Git commit and push successful: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Git commit/push failed: {e.stderr.strip()}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred during git commit/push: {e}")
        raise

# --- JSON File Handling ---
def read_json_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return None

def write_json_file(file_path, data):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logging.info(f"Successfully wrote to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to {file_path}: {e}")
        raise

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
        logging.warning(f"Incomplete swarm_metric_agg condition: {condition}")
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
        logging.info(f"No alive nodes with metric '{metric_name}' found for aggregation.")
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
        logging.warning(f"Unsupported aggregation type: {aggregation_type}")
        return False

    # Evaluate against threshold
    if operator == "gt":
        return aggregated_value > threshold
    elif operator == "lt":
        return aggregated_value < threshold
    elif operator == "eq":
        return aggregated_value == threshold
    # Add other operators as needed
    logging.warning(f"Unsupported operator: {operator}")
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
            logging.info(f"Added task: {task_id}")
            return True
    elif action_type == "REMOVE_TASK":
        original_len = len(current_schedule.get("tasks", []))
        current_schedule["tasks"] = [t for t in current_schedule.get("tasks", []) if t.get("id") != task_id]
        if len(current_schedule["tasks"]) < original_len:
            logging.info(f"Removed task: {task_id}")
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
                logging.info(f"Swapped tasks: {task_id} and {swap_with_task_id}")
                return True
    return False # No change or unsupported action

def main():
    logging.info("Governor renderer started.")
    while True:
        try:
            git_pull_rebase()

            roster = read_json_file("roster.json")
            schedule = read_json_file("schedule.json")
            triggers = read_json_file("triggers.json")

            if not all([roster, schedule, triggers]):
                logging.error("Failed to read one or more essential JSON files. Skipping this cycle.")
                time.sleep(GOVERNOR_LOOP_INTERVAL_SECONDS)
                continue

            original_schedule_str = json.dumps(schedule, indent=2)
            modified_schedule = json.loads(original_schedule_str) # Deep copy

            schedule_changed = False

            for trigger_id, trigger_data in triggers.get("triggers", {}).items():
                condition_met = False
                condition_type = trigger_data.get("condition", {}).get("type")

                if condition_type == "time_based":
                    condition_met = evaluate_condition_time_based(trigger_data["condition"])
                elif condition_type == "swarm_metric_agg":
                    condition_met = evaluate_condition_swarm_metric_agg(trigger_data["condition"], roster)
                # Add other condition types as needed

                if condition_met:
                    logging.info(f"Trigger '{trigger_id}' condition met. Applying actions.")
                    for action in trigger_data.get("actions", []):
                        if apply_action(action, modified_schedule):
                            schedule_changed = True
                else:
                    logging.debug(f"Trigger '{trigger_id}' condition not met.")

            if schedule_changed:
                logging.info("Schedule has been modified by governor. Persisting changes.")
                write_json_file("schedule.json", modified_schedule)
                git_commit_push(f"chore(governor): Applied schedule changes via triggers")
            else:
                logging.info("No schedule changes detected from triggers.")

        except Exception as e:
            logging.error(f"An error occurred in the governor main loop: {e}", exc_info=True)

        time.sleep(GOVERNOR_LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
