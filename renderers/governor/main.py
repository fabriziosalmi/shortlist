#!/usr/bin/env python3
"""
Shortlist Governor - Strategic Adaptation Engine

This headless renderer monitors swarm metrics and applies strategic rules
defined in triggers.json to dynamically modify schedule.json when needed.
"""

import json
import time
import subprocess
import copy
import os
from datetime import datetime, timezone
from dateutil import parser as date_parser

# Configuration
SLEEP_INTERVAL = int(os.getenv("GOVERNOR_INTERVAL", "60"))  # seconds
ROSTER_FILE = "/app/data/roster.json"
SCHEDULE_FILE = "/app/data/schedule.json"
TRIGGERS_FILE = "/app/data/triggers.json"

def run_command(command):
    """Execute a shell command safely"""
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True, shell=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Command failed: {command}")
        print(f"   Error: {e.stderr}")
        return None

def read_json_file(filepath):
    """Read JSON file with error handling"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ Could not read {filepath}: {e}")
        return None

def write_json_file(filepath, data):
    """Write JSON file safely"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Could not write {filepath}: {e}")
        return False

def get_alive_nodes(roster):
    """Filter nodes that are considered alive (last seen within 5 minutes)"""
    if not roster or "nodes" not in roster:
        return []

    now = datetime.now(timezone.utc)
    alive_nodes = []

    for node in roster["nodes"]:
        try:
            last_seen = date_parser.parse(node["last_seen"])
            if (now - last_seen).total_seconds() < 300:  # 5 minutes
                alive_nodes.append(node)
        except Exception as e:
            print(f"⚠️ Error parsing last_seen for node {node.get('id', 'unknown')}: {e}")

    return alive_nodes

def calculate_metric_aggregate(nodes, metric_name, aggregate_type):
    """Calculate aggregate metrics from alive nodes"""
    values = []

    for node in nodes:
        if "metrics" in node and metric_name in node["metrics"]:
            try:
                value = float(node["metrics"][metric_name])
                values.append(value)
            except (ValueError, TypeError):
                continue

    if not values:
        return None

    if aggregate_type == "average":
        return sum(values) / len(values)
    elif aggregate_type == "max":
        return max(values)
    elif aggregate_type == "min":
        return min(values)
    else:
        print(f"⚠️ Unknown aggregate type: {aggregate_type}")
        return None

def evaluate_time_condition(condition):
    """Evaluate time-based trigger conditions"""
    now = datetime.now()

    if "hour_range" in condition:
        start_hour, end_hour = condition["hour_range"]
        current_hour = now.hour
        if start_hour <= end_hour:
            return start_hour <= current_hour <= end_hour
        else:  # Range crosses midnight
            return current_hour >= start_hour or current_hour <= end_hour

    if "weekday" in condition:
        # 0=Monday, 6=Sunday
        return now.weekday() in condition["weekday"]

    return True

def evaluate_swarm_metric_condition(condition, alive_nodes):
    """Evaluate swarm metric-based trigger conditions"""
    metric = condition.get("metric")
    aggregate = condition.get("aggregate", "average")
    threshold = condition.get("threshold")
    operator = condition.get("operator", ">=")

    if not all([metric, threshold is not None]):
        print(f"⚠️ Invalid swarm metric condition: {condition}")
        return False

    actual_value = calculate_metric_aggregate(alive_nodes, metric, aggregate)
    if actual_value is None:
        return False

    if operator == ">=":
        return actual_value >= threshold
    elif operator == "<=":
        return actual_value <= threshold
    elif operator == ">":
        return actual_value > threshold
    elif operator == "<":
        return actual_value < threshold
    elif operator == "==":
        return abs(actual_value - threshold) < 0.1  # Float equality with tolerance
    else:
        print(f"⚠️ Unknown operator: {operator}")
        return False

def apply_schedule_action(schedule, action):
    """Apply an action to modify the schedule"""
    action_type = action.get("type")

    if action_type == "add_task":
        task = action.get("task")
        if task and not any(t.get("id") == task.get("id") for t in schedule.get("tasks", [])):
            schedule.setdefault("tasks", []).append(task)
            return True

    elif action_type == "remove_task":
        task_id = action.get("task_id")
        if task_id:
            tasks = schedule.get("tasks", [])
            original_count = len(tasks)
            schedule["tasks"] = [t for t in tasks if t.get("id") != task_id]
            return len(schedule["tasks"]) != original_count

    elif action_type == "change_priority":
        task_id = action.get("task_id")
        new_priority = action.get("priority")
        if task_id is not None and new_priority is not None:
            for task in schedule.get("tasks", []):
                if task.get("id") == task_id:
                    if task.get("priority") != new_priority:
                        task["priority"] = new_priority
                        return True

    return False

def process_triggers(roster, schedule, triggers):
    """Process all triggers and return modified schedule"""
    if not triggers or "rules" not in triggers:
        return schedule, []

    alive_nodes = get_alive_nodes(roster)
    modified_schedule = copy.deepcopy(schedule)
    applied_triggers = []

    for rule in triggers["rules"]:
        trigger_id = rule.get("id", "unknown")
        condition = rule.get("condition", {})
        action = rule.get("action", {})

        # Evaluate condition
        condition_met = False
        condition_type = condition.get("type")

        if condition_type == "time_based":
            condition_met = evaluate_time_condition(condition)
        elif condition_type == "swarm_metric_agg":
            condition_met = evaluate_swarm_metric_condition(condition, alive_nodes)
        else:
            print(f"⚠️ Unknown condition type for trigger {trigger_id}: {condition_type}")
            continue

        # Apply action if condition is met
        if condition_met:
            if apply_schedule_action(modified_schedule, action):
                applied_triggers.append(trigger_id)
                print(f"✅ Applied trigger: {trigger_id}")
            else:
                print(f"🔄 Trigger {trigger_id} condition met, but action already applied")

    return modified_schedule, applied_triggers

def main():
    """Main governor loop"""
    print("🧠 Starting Shortlist Governor...")
    print(f"   Sleep interval: {SLEEP_INTERVAL} seconds")

    while True:
        try:
            print(f"\n🔍 Governor cycle starting at {datetime.now(timezone.utc).isoformat()}")

            # Update local repository
            print("   📥 Updating repository...")
            if run_command("git pull --rebase") is None:
                print("   ⚠️ Git pull failed, skipping this cycle")
                time.sleep(SLEEP_INTERVAL)
                continue

            # Read current state
            roster = read_json_file(ROSTER_FILE)
            schedule = read_json_file(SCHEDULE_FILE)
            triggers = read_json_file(TRIGGERS_FILE)

            if not all([roster, schedule, triggers]):
                print("   ⚠️ Could not read required files, skipping this cycle")
                time.sleep(SLEEP_INTERVAL)
                continue

            # Process triggers
            original_schedule = copy.deepcopy(schedule)
            modified_schedule, applied_triggers = process_triggers(roster, schedule, triggers)

            # Check if schedule was modified
            if modified_schedule != original_schedule:
                print(f"   📝 Schedule modifications detected from triggers: {applied_triggers}")

                # Write updated schedule
                if write_json_file(SCHEDULE_FILE, modified_schedule):
                    # Commit and push changes
                    trigger_list = ", ".join(applied_triggers)
                    commit_msg = f"chore(governor): Applied triggers: {trigger_list}"

                    run_command("git add schedule.json")
                    if run_command(f'git commit -m "{commit_msg}"'):
                        if run_command("git push"):
                            print(f"   ✅ Successfully applied and pushed schedule changes")
                        else:
                            print("   ⚠️ Failed to push changes")
                    else:
                        print("   ⚠️ Failed to commit changes")
                else:
                    print("   ⚠️ Failed to write modified schedule")
            else:
                print("   ✅ No schedule modifications needed")

        except Exception as e:
            print(f"   🚨 Error in governor cycle: {e}")

        print(f"   😴 Sleeping for {SLEEP_INTERVAL} seconds...")
        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    main()