import json
import os
import uuid
import time
import subprocess
import random
import psutil
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from utils.logging_config import configure_logging
from utils.logging_utils import ComponentLogger, NODE_CONTEXT, log_operation, log_execution_time, log_state_change

# --- Configuration ---
NODE_ID_FILE = f".node_id_{os.getpid()}"
ROSTER_FILE = "roster.json"
SCHEDULE_FILE = "schedule.json"
ASSIGNMENTS_FILE = "assignments.json"

HEARTBEAT_INTERVAL = timedelta(minutes=5)
TASK_HEARTBEAT_INTERVAL = timedelta(seconds=1) # Run more heartbeats in testing
TASK_EXPIRATION = timedelta(seconds=90) # A task is orphaned if its heartbeat is older than 90s
IDLE_PULL_INTERVAL = timedelta(seconds=30)
JITTER_MILLISECONDS = 5000

# Configure logging
configure_logging('node', log_level="INFO")

# --- State Machine States ---
class NodeState:
    IDLE = "IDLE"
    ATTEMPT_CLAIM = "ATTEMPT_CLAIM"
    ACTIVE = "ACTIVE"

# --- Git Operations ---
def run_command(command: list[str], suppress_errors: bool = False) -> str:
    logger = ComponentLogger('node').logger
    cmd_str = ' '.join(command)
    
    with log_operation(logger, 'command_execution', command=cmd_str):
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True, encoding='utf-8')
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                logger.error("Command execution failed",
                            command=cmd_str,
                            stderr=e.stderr,
                            exit_code=e.returncode)
            raise

def git_pull():
    run_command(['git', 'pull'])

def git_push():
    run_command(['git', 'push'])

def commit_and_push(files, message):
    run_command(['git', 'add'] + files)
    status_result = run_command(['git', 'status', '--porcelain'])
    if any(file in status_result for file in files):
        run_command(['git', 'commit', '-m', message])
        git_push()
        return True
    return False

# --- State Management ---
def get_node_id():
    if os.path.exists(NODE_ID_FILE):
        with open(NODE_ID_FILE, 'r') as f:
            return f.read().strip()
    node_id = str(uuid.uuid4())
    with open(NODE_ID_FILE, 'w') as f:
        f.write(node_id)
    print(f"🎉 New node ID generated: {node_id}")
    return node_id

def read_json_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# --- State Machine Logic ---
class Node(ComponentLogger):
    def __init__(self):
        super().__init__('node')
        self.node_id = get_node_id()
        self.state = NodeState.IDLE
        self.current_task = None
        self.last_roster_heartbeat = None
        
        # Add persistent context
        self.logger.add_context(
            node_id=self.node_id,
            **NODE_CONTEXT
        )
        
        self.log_startup(
            state=self.state,
            node_id_short=self.node_id[:8]
        )

    def _recover_and_reset(self, error_source: str) -> None:
        self.logger.error("Emergency reset initiated", error_source=error_source)
        
        try:
            with log_operation(self.logger, "emergency_reset"):
                main_branch = run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], suppress_errors=True).strip()
                if not main_branch:
                    main_branch = 'main'  # Fallback
                run_command(['git', 'fetch', 'origin'])
                run_command(['git', 'reset', '--hard', f'origin/{main_branch}'])
                self.logger.info("Local repository reset completed")
        except Exception as reset_e:
            self.logger.critical("Emergency reset failed", error=str(reset_e))
        finally:
            old_state = self.state
            self.state = NodeState.IDLE
            self.current_task = None
            
            log_state_change(self.logger, "node_state", old_state, self.state)
            self.logger.info("Waiting before retry", wait_seconds=15)
            time.sleep(15)

    def run(self) -> None:
        while True:
            try:
                with log_operation(self.logger, "state_execution", current_state=self.state):
                    if self.state == NodeState.IDLE:
                        self.run_idle_state()
                    elif self.state == NodeState.ATTEMPT_CLAIM:
                        self.run_attempt_claim_state()
                    elif self.state == NodeState.ACTIVE:
                        self.run_active_state()
            except subprocess.CalledProcessError as e:
                self._recover_and_reset(f"Git operation: {' '.join(e.cmd)}")
            except Exception as e:
                self.logger.critical("Unhandled error in main loop",
                                   error=str(e),
                                   error_type=type(e).__name__)
                old_state = self.state
                self.state = NodeState.IDLE
                log_state_change(self.logger, "node_state", old_state, self.state)
                time.sleep(30)

    @log_execution_time
    def run_idle_state(self) -> None:
        # Roster heartbeat if needed
        if not self.last_roster_heartbeat or (datetime.now(timezone.utc) - self.last_roster_heartbeat) > HEARTBEAT_INTERVAL:
            self.perform_roster_heartbeat()

        self.logger.info("Checking available tasks")
        git_pull()
        
        schedule = read_json_file(SCHEDULE_FILE) or {"tasks": []}
        sorted_tasks = sorted(schedule.get("tasks", []), key=lambda x: x.get("priority", 999))
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}

        assigned_tasks = set(assignments.get("assignments", {}).keys())
        now = datetime.now(timezone.utc)

        candidate_task = None
        for task in sorted_tasks:
            task_id = task["id"]
            if task_id not in assigned_tasks:
                print(f"    - Free task found: {task_id}")
                candidate_task = task
                break # Prendi il primo libero
            else:
                # Controlla se il task è orfano
                assignment = assignments["assignments"][task_id]
                heartbeat_time = datetime.fromisoformat(assignment["task_heartbeat"])
                if (now - heartbeat_time) > TASK_EXPIRATION:
                    print(f"    - Orphaned task found: {task_id} (last heartbeat: {heartbeat_time})")
                    candidate_task = task
                    break
        
        if candidate_task:
            self.current_task = candidate_task
            self.state = NodeState.ATTEMPT_CLAIM
        else:
            print(f"[{self.state}] No free or orphaned tasks. Waiting {IDLE_PULL_INTERVAL.seconds}s.")
            time.sleep(IDLE_PULL_INTERVAL.seconds)

    @log_execution_time
    def run_attempt_claim_state(self) -> None:
        task_id = self.current_task['id']
        self.logger.info("Attempting to claim task", task_id=task_id)
        
        # Jitter
        wait_ms = random.randint(0, JITTER_MILLISECONDS)
        self.logger.debug("Applying jitter delay", wait_ms=wait_ms)
        time.sleep(wait_ms / 1000.0)

        # Pull finale prima del tentativo
        git_pull()

        # Recheck if the task is still available
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
        if self.current_task['id'] in assignments["assignments"]:
             # Check if it's orphaned, otherwise it was taken
            assignment = assignments["assignments"][self.current_task['id']]
            heartbeat_time = datetime.fromisoformat(assignment.get("task_heartbeat", "1970-01-01T00:00:00+00:00"))
            if (datetime.now(timezone.utc) - heartbeat_time) < TASK_EXPIRATION:
                print(f"    - Task {self.current_task['id']} has been claimed by another node. Returning to IDLE.")
                self.state = NodeState.IDLE
                return

        # Claim the task
        now_iso = datetime.now(timezone.utc).isoformat()
        assignments.setdefault("assignments", {})[self.current_task['id']] = {
            "node_id": self.node_id,
            "claimed_at": now_iso,
            "task_heartbeat": now_iso,
            "status": "claiming"
        }
        # Write to assignments file, using cwd as base
        assignments_path = os.path.join(os.getcwd(), ASSIGNMENTS_FILE)
        with open(assignments_path, 'w') as f:
            json.dump(assignments, f, indent=2)

        commit_message = f"feat(assignments): node {self.node_id[:8]} claims {self.current_task['id']}"
        if commit_and_push([ASSIGNMENTS_FILE], commit_message):
            print(f"    - ✅ Successfully claimed {self.current_task['id']}!")
            self.state = NodeState.ACTIVE
        else:
            print("    - No changes to commit. Returning to IDLE.")
            self.state = NodeState.IDLE

    @log_execution_time
    def run_active_state(self) -> None:
        task_id = self.current_task['id']
        task_type = self.current_task['type']
        
        with self.logger.context_bind(task_id=task_id, task_type=task_type):
            self.logger.info("Executing task")

            renderer_path = f"renderers/{task_type}"
            image_name = f"shortlist-{task_type}-renderer"

            if not os.path.exists(renderer_path):
                self.logger.error("Renderer not found", renderer_path=renderer_path)
                old_state = self.state
                self.state = NodeState.IDLE
                log_state_change(self.logger, "node_state", old_state, self.state)
                return

        try:
            # Build Docker image for the renderer
            print(f"    - Building Docker image: {image_name}...")
            run_command(['docker', 'build', '-t', image_name, renderer_path])

            # Prepare volumes and port mapping
            port_mapping = []
            if task_type == 'governor' or task_type == 'healer':
                # Governor and Healer need full access to the repo for git operations and file manipulation
                volumes = [
                    '-v', f'{os.path.abspath(".")}:/app',
                ]
            else:
                # Default volumes for other renderers
                volumes = [
                    '-v', f'{os.path.abspath("shortlist.json")}:/app/data/shortlist.json:ro', # Read shortlist
                ]
                if task_type == 'dashboard':
                    volumes += [
                        '-v', f'{os.path.abspath("roster.json")}:/app/data/roster.json:ro',
                        '-v', f'{os.path.abspath("schedule.json")}:/app/data/schedule.json:ro',
                        '-v', f'{os.path.abspath("assignments.json")}:/app/data/assignments.json:ro',
                    ]
                
                # Specific volumes and port mappings
                if task_type == 'audio':
                    port_mapping = ['-p', '8001:8000']
                    volumes += [
                        '-v', f'{os.path.abspath("./output")}:/app/output',
                    ]
                elif task_type == 'dashboard':
                    port_mapping = ['-p', '8000:8000']
                    volumes += [
                        '-v', f'{os.path.abspath("./output")}:/app/output', # Dashboard also writes to output
                    ]
                elif task_type == 'video':
                    port_mapping = ['-p', '8002:8000']
                    volumes += [
                        '-v', f'{os.path.abspath("./output")}:/app/output',
                    ]
                elif task_type == 'web':
                    port_mapping = ['-p', '8003:8000']
                    volumes += [
                        '-v', f'{os.path.abspath("./output")}:/app/data', # This is different from /app/output
                    ]
                elif task_type == 'api':
                    port_mapping = ['-p', '8004:8000']
                    volumes += [
                        '-v', f'{os.path.abspath("./output")}:/app/data', # This is different from /app/output
                    ]
                elif task_type == 'admin_ui':
                    port_mapping = ['-p', '8005:8000']
                    volumes += [
                        '-v', f'{os.path.abspath(".")}:/app/data', # This mounts the whole repo to /app/data
                    ]

            # Prepare environment variables for API container
            env_vars = []
            if task_type == 'api':
                # Pass governance API environment variables if available
                for env_var in ['GIT_AUTH_TOKEN', 'GITHUB_REPO', 'MAINTAINER_API_TOKEN', 'CONTRIBUTOR_API_TOKEN']:
                    value = os.getenv(env_var)
                    if value:
                        env_vars.extend(['-e', f'{env_var}={value}'])

            # Start the renderer container
            print(f"    - Starting container from image: {image_name}...")
            container_id = run_command([
                'docker', 'run', '-d',
                '--name', f'{task_id}-{self.node_id[:8]}', # Unique name for container
            ] + volumes + port_mapping + env_vars + [image_name])
            print(f"    - Container {container_id[:12]} started.")
            print(f"    - Docker run output: {container_id}")

        except Exception as e:
            print(f"    - 🚨 Error managing Docker: {e}. Returning to IDLE.")
            self.state = NodeState.IDLE
            return

        # Monitoring and heartbeat loop
        while True:
            # Check if container is still active
            running_containers = run_command(['docker', 'ps', '-q', '--filter', f'id={container_id}'])
            if not running_containers:
                print(f"    - ‼️ Renderer container has stopped. Releasing task.")
                break

            print(f"    - [{task_id}] Renderer is active. Performing task heartbeat...")
            
            try:
                # ... (heartbeat logic remains the same) ...
                git_pull()
                assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
                current_assignment = assignments.get("assignments", {}).get(task_id)
                if not current_assignment or current_assignment["node_id"] != self.node_id:
                    print(f"    - ‼️ Lost assignment for task {task_id}. Stopping renderer.")
                    run_command(['docker', 'stop', container_id], suppress_errors=True)
                    run_command(['docker', 'rm', container_id], suppress_errors=True)
                    break

                assignments["assignments"][task_id]["task_heartbeat"] = datetime.now(timezone.utc).isoformat()
                assignments["assignments"][task_id]["status"] = "streaming"
                # Write to assignments file, using cwd as base
                assignments_path = os.path.join(os.getcwd(), ASSIGNMENTS_FILE)
                with open(assignments_path, 'w') as f:
                    json.dump(assignments, f, indent=2)
                
                commit_message = f"chore(assignments): task heartbeat for {task_id} from node {self.node_id[:8]}"
                commit_and_push([ASSIGNMENTS_FILE], commit_message)

            except Exception as e:
                print(f"    - 🚨 Error during task heartbeat: {e}. Stopping renderer.")
                run_command(['docker', 'stop', container_id], suppress_errors=True)
                run_command(['docker', 'rm', container_id], suppress_errors=True)
                break
            
            time.sleep(TASK_HEARTBEAT_INTERVAL.seconds)

        # Final cleanup in case of loop exit
        try:
            print(f"    - Cleaning up container {container_id[:12]}...")
            run_command(['docker', 'stop', container_id], suppress_errors=True)
            run_command(['docker', 'rm', container_id], suppress_errors=True)
        except Exception as e:
            print(f"    - Error during container cleanup: {e}")

        # End of work, return to IDLE
        print(f"Task {task_id} finished. Returning to IDLE.")
        self.current_task = None
        self.state = NodeState.IDLE

    @log_execution_time
    def perform_roster_heartbeat(self) -> None:
        self.logger.info("Performing roster heartbeat")
        try:
            with log_operation(self.logger, "roster_heartbeat"):
                git_pull()
                roster = read_json_file(ROSTER_FILE) or {"nodes": []}

            # Collect system metrics
            try:
                cpu_load = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                metrics = {
                    "cpu_load": round(cpu_load, 1),
                    "memory_percent": round(memory_percent, 1)
                }
                print(f"    - System metrics: CPU {cpu_load}%, Memory {memory_percent}%")
            except Exception as e:
                print(f"    - ⚠️ Could not collect metrics: {e}")
                metrics = {
                    "cpu_load": 0.0,
                    "memory_percent": 0.0
                }

            node_found = False
            current_time = datetime.now(timezone.utc).isoformat()

            for node in roster["nodes"]:
                if node["id"] == self.node_id:
                    node["last_seen"] = current_time
                    node["metrics"] = metrics
                    node_found = True
                    break

            if not node_found:
                roster["nodes"].append({
                    "id": self.node_id,
                    "started_at": current_time,
                    "last_seen": current_time,
                    "metrics": metrics
                })
            
            # Write to roster file, using cwd as base
            roster_path = os.path.join(os.getcwd(), ROSTER_FILE)
            with open(roster_path, 'w') as f:
                json.dump(roster, f, indent=2)

            commit_message = f"chore(roster): heartbeat from node {self.node_id[:8]}"
            commit_and_push([ROSTER_FILE], commit_message)
            self.last_roster_heartbeat = datetime.now(timezone.utc)
        except Exception as e:
            print(f"    - 🚨 Error during roster heartbeat: {e}")

if __name__ == "__main__":
    node = Node()
    node.run()