import os
import time
import json
import subprocess
from datetime import datetime, timedelta
from dateutil.parser import parse as date_parse
from typing import Dict, List, Any, Optional, Set, Tuple

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    HEALER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('healer_renderer', log_level="INFO", log_file='/app/data/healer.log')
logger = ComponentLogger('healer_renderer')
logger.logger.add_context(**HEALER_CONTEXT)

# --- Configuration ---
GIT_REPO_PATH = "."  # Current directory
HEALER_LOOP_INTERVAL_SECONDS = 5 * 60 # 5 minutes
NODE_HEARTBEAT_TIMEOUT_MINUTES = 15 # How recent a node's heartbeat must be to be considered "alive"

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
            subprocess.run(["git", "add", "assignments.json"], cwd=GIT_REPO_PATH, check=True)
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

def main() -> None:
    """Main loop for the healer renderer."""
    logger.log_startup()
    
    while True:
        with log_operation(logger.logger, "healer_cycle"):
            try:
                git_pull_rebase()

            roster = read_json_file("roster.json")
            assignments = read_json_file("assignments.json")

            if not all([roster, assignments]):
                logger.logger.error("Failed to read required files",
                                  roster_exists=bool(roster),
                                  assignments_exists=bool(assignments))
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
                    logger.logger.warning("Detected zombie assignment",
                                         task_id=task_id,
                                         dead_node_id=assigned_node_id)
                    zombie_count += 1
                else:
                    tasks_to_keep.append((task_id, assignment_data))
            
            if zombie_count > 0:
                modified_assignments["tasks"] = {task_id: data for task_id, data in tasks_to_keep}
                assignments_changed = True
                logger.logger.info("Cleared zombie assignments",
                                  zombie_count=zombie_count)

            if assignments_changed:
                logger.logger.info("Assignments modified",
                                  remaining_tasks=len(tasks_to_keep))
                write_json_file("assignments.json", modified_assignments)
                git_commit_push(f"fix(healer): Cleared {zombie_count} zombie task assignments")
            else:
                logger.logger.info("No zombie assignments",
                                  total_tasks=len(modified_assignments.get("tasks", {})))

        except Exception as e:
            logger.logger.error("Error in healer cycle",
                              error=str(e),
                              error_type=type(e).__name__,
                              exc_info=True)

        time.sleep(HEALER_LOOP_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
    logger.log_shutdown()
