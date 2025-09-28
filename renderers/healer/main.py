#!/usr/bin/env python3
"""
Shortlist Healer - Swarm Immune System

This headless renderer continuously monitors the swarm state and automatically
corrects inconsistencies like zombie task assignments from dead nodes.
"""

import json
import time
import subprocess
import os
from datetime import datetime, timezone
from dateutil import parser as date_parser

# Configuration
SLEEP_INTERVAL = int(os.getenv("HEALER_INTERVAL", "300"))  # 5 minutes in seconds
ROSTER_FILE = "/app/data/roster.json"
ASSIGNMENTS_FILE = "/app/data/assignments.json"

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

def get_alive_node_ids(roster):
    """Get set of node IDs that are considered alive"""
    if not roster or "nodes" not in roster:
        return set()

    now = datetime.now(timezone.utc)
    alive_node_ids = set()

    for node in roster["nodes"]:
        try:
            last_seen = date_parser.parse(node["last_seen"])
            # Consider node alive if last seen within 5 minutes
            if (now - last_seen).total_seconds() < 300:
                alive_node_ids.add(node["id"])
        except Exception as e:
            print(f"⚠️ Error parsing last_seen for node {node.get('id', 'unknown')}: {e}")

    return alive_node_ids

def detect_zombie_assignments(assignments, alive_node_ids):
    """Detect task assignments from dead nodes (zombies)"""
    if not assignments or "assignments" not in assignments:
        return []

    zombie_tasks = []

    for task_id, assignment in assignments["assignments"].items():
        node_id = assignment.get("node_id")
        if node_id and node_id not in alive_node_ids:
            zombie_tasks.append({
                "task_id": task_id,
                "node_id": node_id,
                "assignment": assignment
            })

    return zombie_tasks

def detect_stale_assignments(assignments):
    """Detect assignments with very old heartbeats (over 10 minutes)"""
    if not assignments or "assignments" not in assignments:
        return []

    now = datetime.now(timezone.utc)
    stale_tasks = []

    for task_id, assignment in assignments["assignments"].items():
        try:
            task_heartbeat = assignment.get("task_heartbeat")
            if task_heartbeat:
                last_heartbeat = date_parser.parse(task_heartbeat)
                # Consider assignment stale if no heartbeat for over 10 minutes
                if (now - last_heartbeat).total_seconds() > 600:
                    stale_tasks.append({
                        "task_id": task_id,
                        "node_id": assignment.get("node_id"),
                        "last_heartbeat": task_heartbeat,
                        "assignment": assignment
                    })
        except Exception as e:
            print(f"⚠️ Error parsing heartbeat for task {task_id}: {e}")

    return stale_tasks

def heal_assignments(assignments, zombie_tasks, stale_tasks):
    """Remove zombie and stale assignments from assignments data"""
    if not assignments or "assignments" not in assignments:
        return assignments, False

    healed_assignments = assignments.copy()
    modifications_made = False

    # Remove zombie assignments
    for zombie in zombie_tasks:
        task_id = zombie["task_id"]
        if task_id in healed_assignments["assignments"]:
            del healed_assignments["assignments"][task_id]
            modifications_made = True
            print(f"   🧹 Removed zombie assignment: {task_id} (node: {zombie['node_id'][:8]}...)")

    # Remove stale assignments
    for stale in stale_tasks:
        task_id = stale["task_id"]
        if task_id in healed_assignments["assignments"]:
            del healed_assignments["assignments"][task_id]
            modifications_made = True
            print(f"   🧹 Removed stale assignment: {task_id} (last heartbeat: {stale['last_heartbeat']})")

    return healed_assignments, modifications_made

def main():
    """Main healer loop"""
    print("🩺 Starting Shortlist Healer...")
    print(f"   Sleep interval: {SLEEP_INTERVAL} seconds")

    while True:
        try:
            print(f"\n🔍 Healer scan starting at {datetime.now(timezone.utc).isoformat()}")

            # Update local repository
            print("   📥 Updating repository...")
            if run_command("git pull --rebase") is None:
                print("   ⚠️ Git pull failed, skipping this scan")
                time.sleep(SLEEP_INTERVAL)
                continue

            # Read current state
            roster = read_json_file(ROSTER_FILE)
            assignments = read_json_file(ASSIGNMENTS_FILE)

            if not all([roster, assignments]):
                print("   ⚠️ Could not read required files, skipping this scan")
                time.sleep(SLEEP_INTERVAL)
                continue

            # Get alive nodes
            alive_node_ids = get_alive_node_ids(roster)
            print(f"   💚 Found {len(alive_node_ids)} alive nodes")

            # Detect anomalies
            zombie_tasks = detect_zombie_assignments(assignments, alive_node_ids)
            stale_tasks = detect_stale_assignments(assignments)

            total_issues = len(zombie_tasks) + len(stale_tasks)

            if total_issues > 0:
                print(f"   🚨 Detected {len(zombie_tasks)} zombie assignments and {len(stale_tasks)} stale assignments")

                # Apply healing
                healed_assignments, modifications_made = heal_assignments(assignments, zombie_tasks, stale_tasks)

                if modifications_made:
                    # Write healed assignments
                    if write_json_file(ASSIGNMENTS_FILE, healed_assignments):
                        # Commit and push changes
                        commit_msg = f"fix(healer): Cleared {len(zombie_tasks)} zombie and {len(stale_tasks)} stale task assignments"

                        run_command("git add assignments.json")
                        if run_command(f'git commit -m "{commit_msg}"'):
                            if run_command("git push"):
                                print(f"   ✅ Successfully healed and pushed assignment corrections")
                            else:
                                print("   ⚠️ Failed to push healing changes")
                        else:
                            print("   ⚠️ Failed to commit healing changes")
                    else:
                        print("   ⚠️ Failed to write healed assignments")
                else:
                    print("   🔄 Issues detected but no modifications needed")
            else:
                print("   ✅ No anomalies detected - swarm is healthy")

        except Exception as e:
            print(f"   🚨 Error in healer scan: {e}")

        print(f"   😴 Sleeping for {SLEEP_INTERVAL} seconds...")
        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    main()