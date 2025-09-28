import os
import time
import json
import logging
import subprocess
from datetime import datetime, timedelta
from dateutil.parser import parse as date_parse

# --- Configuration ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

GIT_REPO_PATH = "." # Current directory
HEALER_LOOP_INTERVAL_SECONDS = 5 * 60 # 5 minutes
NODE_HEARTBEAT_TIMEOUT_MINUTES = 15 # How recent a node's heartbeat must be to be considered "alive"

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
        subprocess.run(["git", "add", "assignments.json"], cwd=GIT_REPO_PATH, check=True)
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

def main():
    logging.info("Healer renderer started.")
    while True:
        try:
            git_pull_rebase()

            roster = read_json_file("roster.json")
            assignments = read_json_file("assignments.json")

            if not all([roster, assignments]):
                logging.error("Failed to read roster.json or assignments.json. Skipping this cycle.")
                time.sleep(HEALER_LOOP_INTERVAL_SECONDS)
                continue

            alive_node_ids = set()
            now = datetime.utcnow()
            for node_id, node_data in roster.get("nodes", {}).items():
                last_seen_str = node_data.get("last_seen")
                if last_seen_str:
                    last_seen = date_parse(last_seen_str)
                    if now - last_seen < timedelta(minutes=NODE_HEARTBEAT_TIMEOUT_MINUTES):
                        alive_node_ids.add(node_id)

            original_assignments_str = json.dumps(assignments, indent=2)
            modified_assignments = json.loads(original_assignments_str) # Deep copy
            assignments_changed = False
            zombie_count = 0

            tasks_to_keep = []
            for task_id, assignment_data in modified_assignments.get("tasks", {}).items():
                assigned_node_id = assignment_data.get("node_id")
                if assigned_node_id and assigned_node_id not in alive_node_ids:
                    logging.warning(f"Detected zombie assignment: Task '{task_id}' assigned to dead node '{assigned_node_id}'.")
                    zombie_count += 1
                else:
                    tasks_to_keep.append((task_id, assignment_data))
            
            if zombie_count > 0:
                modified_assignments["tasks"] = {task_id: data for task_id, data in tasks_to_keep}
                assignments_changed = True
                logging.info(f"Cleared {zombie_count} zombie task assignments.")

            if assignments_changed:
                logging.info("Assignments have been modified by healer. Persisting changes.")
                write_json_file("assignments.json", modified_assignments)
                git_commit_push(f"fix(healer): Cleared {zombie_count} zombie task assignments")
            else:
                logging.info("No zombie assignments detected.")

        except Exception as e:
            logging.error(f"An error occurred in the healer main loop: {e}", exc_info=True)

        time.sleep(HEALER_LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
