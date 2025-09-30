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
from utils.logging_utils import ComponentLogger, NODE_CONTEXT, log_execution_time, log_state_change

# Simple decorator for logging operations
def log_operation_decorator(func):
    def wrapper(self, *args, **kwargs):
        operation_name = func.__name__
        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Operation {operation_name} failed", error=str(e))
            raise
    return wrapper

# Use the decorator as log_operation for backward compatibility
log_operation = log_operation_decorator

# Import regional coordination (optional - graceful fallback if not available)
try:
    from utils.geographic import get_geographic_manager
    from utils.regional_coordinator import RegionalCoordinator
    REGIONAL_SUPPORT = True
except ImportError:
    REGIONAL_SUPPORT = False

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

# Health check configuration
HEALTH_CHECK_INTERVAL = timedelta(seconds=20)  # Check health every 20 seconds
HEALTH_CHECK_TIMEOUT = 3  # Seconds to wait for health check response
MAX_HEALTH_CHECK_FAILURES = 3  # Number of consecutive failures before considering unhealthy

# Renderer configuration
RENDERER_CONFIG = {
    "governor": {
        "image": "shortlist-governor",
        "volumes": ["{repo_root}:/app"],
    },
    "healer": {
        "image": "shortlist-healer",
        "volumes": ["{repo_root}:/app"],
    },
    "api": {
        "image": "shortlist-api",
        "port": 8004,
        "health_check": True,
        "volumes": [
            "{repo_root}/output:/app/data",
            "{repo_root}/secrets:/app/data/secrets:rw"
        ],
        "env_vars": ["MAINTAINER_API_TOKEN", "CONTRIBUTOR_API_TOKEN", "GIT_AUTH_TOKEN"]
    },
    "admin_ui": {
        "image": "shortlist-admin-ui",
        "port": 8005,
        "health_check": True,
        "volumes": ["{repo_root}:/app/data"],
    },
    "dashboard": {
        "image": "shortlist-dashboard",
        "port": 8000,
        "health_check": True,
        "volumes": [
            "{repo_root}/roster.json:/app/data/roster.json:ro",
            "{repo_root}/schedule.json:/app/data/schedule.json:ro",
            "{repo_root}/assignments.json:/app/data/assignments.json:ro",
            "{repo_root}/output:/app/output",
        ],
    },
    "audio": {
        "image": "shortlist-audio",
        "port": 8001,
        "health_check": True,
        "volumes": [
            "{repo_root}/shortlist.json:/app/data/shortlist.json:ro",
            "{repo_root}/output:/app/output",
        ],
    },
    "video": {
        "image": "shortlist-video",
        "port": 8002,
        "health_check": True,
        "volumes": [
            "{repo_root}/shortlist.json:/app/data/shortlist.json:ro",
            "{repo_root}/output:/app/output",
        ],
    },
    "web": {
        "image": "shortlist-web",
        "port": 8003,
        "health_check": True,
        "volumes": [
            "{repo_root}/shortlist.json:/app/data/shortlist.json:ro",
            "{repo_root}/output:/app/data",
        ],
    },
    "text": {
        "image": "shortlist-text",
        "volumes": ["{repo_root}/shortlist.json:/app/data/shortlist.json:ro"],
    },
    "metrics_exporter": {
        "image": "shortlist-metrics-exporter",
        "port": 9091,
        "health_check": True,
        "volumes": [
            "{repo_root}:/app/data",
            "{repo_root}/output:/app/output",
            "{repo_root}/config:/app/config"
        ],
    },
}

# Configure logging
configure_logging('node', log_level="INFO")

# --- State Machine States ---
class NodeState:
    IDLE = "IDLE"
    ATTEMPT_CLAIM = "ATTEMPT_CLAIM"
    ACTIVE = "ACTIVE"

# --- Docker Management ---
class DockerManager:
    """Manages Docker container lifecycle and health checks for renderers."""
    
    def __init__(self, task_type: str, task_id: str, node_id: str, logger: Any) -> None:
        """Initialize Docker manager for a renderer.
        
        Args:
            task_type: Type of renderer (e.g., 'admin_ui', 'api')
            task_id: Unique task ID
            node_id: ID of the managing node
            logger: Logger instance for structured logging
        """
        self.task_type = task_type
        self.task_id = task_id
        self.node_id = node_id
        self.logger = logger
        self.container_id = None
        self.health_check_failures = 0
        
        # Get renderer config
        self.config = RENDERER_CONFIG.get(task_type, {})
        if not self.config:
            raise ValueError(f"No configuration found for renderer type: {task_type}")
        
        # Prepare container name
        self.container_name = f"{task_id}-{node_id[:8]}"
        
        # Replace {repo_root} in volume mappings
        repo_root = os.path.abspath(".")
        self.config['volumes'] = [
            v.replace("{repo_root}", repo_root) for v in self.config.get('volumes', [])
        ]
    
    @log_operation
    def build_image(self) -> None:
        """Build Docker image for the renderer."""
        renderer_path = f"renderers/{self.task_type}"
        if not os.path.exists(renderer_path):
            raise FileNotFoundError(f"Renderer path not found: {renderer_path}")
        
        run_command(['docker', 'build', '-t', self.config['image'], renderer_path])
    
    @log_operation
    def start_container(self) -> str:
        """Start the renderer container.
        
        Returns:
            str: Container ID
        """
        command = ['docker', 'run', '-d', '--name', self.container_name]

        # Inject environment variables from OS env or secrets file
        try:
            secrets_path = os.path.join(os.path.abspath('.'), 'secrets', 'secrets.json')
            secrets = {}
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r') as f:
                    secrets = json.load(f) if f else {}
        except Exception:
            secrets = {}

        required_env = self.config.get('env_vars', [])
        for var in required_env:
            val = os.getenv(var)
            if not val:
                val = secrets.get(var)
            if val:
                command.extend(['-e', f'{var}={val}'])
            else:
                self.logger.warning("Missing optional environment variable for renderer",
                                    variable=var, task_type=self.task_type)
        
        # Add port mapping if configured
        if 'port' in self.config:
            command.extend(['-p', f"{self.config['port']}:8000"])
        
        # Add volume mappings
        for volume in self.config.get('volumes', []):
            command.extend(['-v', volume])
        
        # Add environment variables for API
        if self.task_type == 'api':
            for env_var in ['GIT_AUTH_TOKEN', 'GITHUB_REPO', 'MAINTAINER_API_TOKEN', 'CONTRIBUTOR_API_TOKEN']:
                value = os.getenv(env_var)
                if value:
                    command.extend(['-e', f"{env_var}={value}"])
        
        # Start container
        command.append(self.config['image'])
        result = run_command(command)
        self.container_id = result.strip()
        return self.container_id
    
    def is_running(self) -> bool:
        """Check if the container is still running."""
        if not self.container_id:
            return False
        
        try:
            result = run_command(['docker', 'ps', '-q', '--filter', f'id={self.container_id}'])
            return bool(result.strip())
        except Exception:
            return False
    
    @log_operation
    def check_health(self) -> bool:
        """Perform health check if supported.
        
        Returns:
            bool: True if healthy or health checks not supported
        """
        if not self.config.get('health_check'):
            return True
        
        if not self.is_running():
            return False
        
        try:
            import requests
            port = self.config['port']
            url = f"http://localhost:{port}/health"
            
            response = requests.get(url, timeout=HEALTH_CHECK_TIMEOUT)
            
            if response.status_code == 200:
                self.health_check_failures = 0
                self.logger.info("Health check succeeded",
                               task_id=self.task_id,
                               port=port)
                return True
            else:
                self.health_check_failures += 1
                self.logger.warning("Health check failed",
                                task_id=self.task_id,
                                port=port,
                                status_code=response.status_code)
        except Exception as e:
            self.health_check_failures += 1
            self.logger.error("Health check error",
                           error=str(e),
                           error_type=type(e).__name__,
                           task_id=self.task_id)
        
        return self.health_check_failures < MAX_HEALTH_CHECK_FAILURES
    
    @log_operation
    def stop_container(self) -> None:
        """Stop and remove the container."""
        if self.container_id:
            try:
                run_command(['docker', 'stop', self.container_id], suppress_errors=True)
                run_command(['docker', 'rm', self.container_id], suppress_errors=True)
            except Exception as e:
                self.logger.error("Failed to stop container",
                               error=str(e),
                               error_type=type(e).__name__,
                               container_id=self.container_id)
            finally:
                self.container_id = None

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

        # Initialize regional coordination if available
        self.regional_coordinator = None
        self.geo_manager = None

        if REGIONAL_SUPPORT:
            try:
                from utils.git_manager import GitManager
                self.geo_manager = get_geographic_manager()

                # Create a simple GitManager wrapper for existing functions
                class SimpleGitManager(GitManager):
                    def sync(self):
                        git_pull()
                        return True

                    def commit_and_push(self, files, message):
                        git_push()
                        return True

                    def read_file(self, path):
                        with open(path, 'r') as f:
                            return f.read()

                    def write_file(self, path, content):
                        with open(path, 'w') as f:
                            f.write(content)

                    def read_json(self, path):
                        return read_json_file(path)

                    def write_json(self, path, data):
                        write_json_file(path, data)

                    def read_json_file(self, filename):
                        return read_json_file(filename)

                    def write_json_file(self, filename, data, message=None):
                        write_json_file(filename, data)
                        if message:
                            git_push()
                        return True

                git_manager = SimpleGitManager()
                self.regional_coordinator = RegionalCoordinator(git_manager)

                print(f"    ✅ Regional support enabled: {self.geo_manager.current_region}")
            except Exception as e:
                print(f"    ⚠️ Failed to initialize regional support: {e}")

        # Add persistent context
        context = {
            'node_id': self.node_id,
            **NODE_CONTEXT
        }

        if self.geo_manager:
            context['region'] = self.geo_manager.current_region

        self.logger.add_context(**context)

        self.log_startup(
            state=self.state,
            node_id_short=self.node_id[:8],
            regional_support=REGIONAL_SUPPORT,
            region=self.geo_manager.current_region if self.geo_manager else 'default'
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

        # Use regional coordinator if available, otherwise fall back to legacy behavior
        if self.regional_coordinator:
            success = self._attempt_claim_with_regional_coordinator()
        else:
            success = self._attempt_claim_legacy()

        if success:
            print(f"    - ✅ Successfully claimed {self.current_task['id']}!")
            self.state = NodeState.ACTIVE
        else:
            print(f"    - Failed to claim {self.current_task['id']}. Returning to IDLE.")
            self.state = NodeState.IDLE

    def _attempt_claim_with_regional_coordinator(self) -> bool:
        """Attempt to claim task using regional coordinator."""

        # Jitter
        wait_ms = random.randint(0, JITTER_MILLISECONDS)
        self.logger.debug("Applying jitter delay", wait_ms=wait_ms)
        time.sleep(wait_ms / 1000.0)

        # Check if we can claim this task regionally
        can_claim, reason = self.regional_coordinator.can_claim_task(self.current_task, self.node_id)
        if not can_claim:
            self.logger.info("Cannot claim task due to regional constraints", {
                'task_id': self.current_task['id'],
                'reason': reason
            })
            return False

        # Attempt to claim with lease
        lease_duration = timedelta(minutes=5)  # 5 minute lease
        return self.regional_coordinator.claim_task(self.current_task, self.node_id, lease_duration)

    def _attempt_claim_legacy(self) -> bool:
        """Attempt to claim task using legacy behavior."""

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
                return False

        # Claim the task
        now_iso = datetime.now(timezone.utc).isoformat()
        task_assignment = {
            "node_id": self.node_id,
            "claimed_at": now_iso,
            "task_heartbeat": now_iso,
            "status": "claiming"
        }

        # Add regional context if geo_manager is available
        if self.geo_manager:
            task_assignment["region"] = self.geo_manager.current_region

        assignments.setdefault("assignments", {})[self.current_task['id']] = task_assignment

        # Write to assignments file, using cwd as base
        assignments_path = os.path.join(os.getcwd(), ASSIGNMENTS_FILE)
        with open(assignments_path, 'w') as f:
            json.dump(assignments, f, indent=2)

        commit_message = f"feat(assignments): node {self.node_id[:8]} claims {self.current_task['id']}"
        return commit_and_push([ASSIGNMENTS_FILE], commit_message)

    @log_execution_time
    def run_active_state(self) -> None:
        task_id = self.current_task['id']
        task_type = self.current_task['type']
        
        with self.logger.context_bind(task_id=task_id, task_type=task_type):
            self.logger.info("Executing task")
            
            try:
                # Initialize Docker manager
                docker_manager = DockerManager(task_type, task_id, self.node_id, self.logger)

                # Build and start container
                docker_manager.build_image()
                container_id = docker_manager.start_container()
                
                self.logger.info("Container started",
                               container_id=container_id[:12])
                
                # Monitoring and health check loop
                last_health_check = datetime.now(timezone.utc)
                
                while True:
                    now = datetime.now(timezone.utc)
                    
                    # Check container health
                    if now - last_health_check >= HEALTH_CHECK_INTERVAL:
                        if not docker_manager.is_running():
                            self.logger.warning("Container stopped unexpectedly",
                                            container_id=container_id[:12])
                            break
                        
                        if not docker_manager.check_health():
                            self.logger.error("Health check failed too many times",
                                           container_id=container_id[:12],
                                           failures=docker_manager.health_check_failures)
                            break
                        
                        last_health_check = now
                    
                    # Perform task heartbeat
                    with log_operation(self.logger, "task_heartbeat"):
                        git_pull()
                        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
                        current_assignment = assignments.get("assignments", {}).get(task_id)
                        
                        if not current_assignment or current_assignment["node_id"] != self.node_id:
                            self.logger.warning("Lost task assignment")
                            break
                        
                        assignments["assignments"][task_id]["task_heartbeat"] = now.isoformat()
                        assignments["assignments"][task_id]["status"] = "streaming"
                        
                        with open(ASSIGNMENTS_FILE, 'w') as f:
                            json.dump(assignments, f, indent=2)
                        
                        commit_message = f"chore(assignments): task heartbeat for {task_id} from node {self.node_id[:8]}"
                        commit_and_push([ASSIGNMENTS_FILE], commit_message)
                    
                    time.sleep(TASK_HEARTBEAT_INTERVAL.seconds)
                
                # Clean up
                docker_manager.stop_container()
                
            except Exception as e:
                self.logger.error("Error in active state",
                               error=str(e),
                               error_type=type(e).__name__)
                if 'docker_manager' in locals():
                    docker_manager.stop_container()

            # End of work, return to IDLE
            self.logger.info("Task finished")
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
                    # Add regional context if available
                    if self.geo_manager:
                        node["region"] = self.geo_manager.current_region
                    node_found = True
                    break

            if not node_found:
                new_node = {
                    "id": self.node_id,
                    "started_at": current_time,
                    "last_seen": current_time,
                    "metrics": metrics
                }
                # Add regional context if available
                if self.geo_manager:
                    new_node["region"] = self.geo_manager.current_region

                roster["nodes"].append(new_node)
            
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
    import argparse

    parser = argparse.ArgumentParser(description='Shortlist Node with Geographic Distribution Support')
    parser.add_argument('--region',
                       help='Override region detection (e.g., us-east, eu-west, asia-pacific)',
                       default=None)
    parser.add_argument('--roles',
                       help='Comma-separated list of roles (for compatibility with existing role system)',
                       default=None)
    parser.add_argument('--enable-geo-sharding',
                       action='store_true',
                       help='Enable geographic sharding (requires geographic_config.json)')

    args = parser.parse_args()

    # Set region override if specified
    if args.region:
        os.environ['SHORTLIST_REGION'] = args.region
        print(f"🌍 Region override: {args.region}")

    # Enable geographic sharding if requested
    if args.enable_geo_sharding:
        print("🗺️ Geographic sharding enabled")

    # Print banner with geographic information
    if REGIONAL_SUPPORT:
        try:
            from utils.geographic import get_geographic_manager
            geo_manager = get_geographic_manager()
            print(f"🚀 Starting Shortlist Node")
            print(f"   Region: {geo_manager.current_region}")
            print(f"   Geographic Sharding: {'Enabled' if geo_manager.is_sharding_enabled() else 'Disabled'}")
            if args.roles:
                print(f"   Roles: {args.roles}")
            print()
        except Exception as e:
            print(f"⚠️ Geographic support initialization failed: {e}")
            print("   Falling back to single-region mode")
            print()
    else:
        print("🚀 Starting Shortlist Node (single-region mode)")
        if args.roles:
            print(f"   Roles: {args.roles}")
        print()

    node = Node()
    node.run()