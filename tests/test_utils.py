"""Test utilities, factories, and constants for shortlist tests."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union
import json

# --- Constants ---
TEST_NODE_ID = "test-node-id"
BASE_DATETIME = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# File paths using pathlib
REPO_ROOT = Path(__file__).parent.parent
NODE_PY = REPO_ROOT / "node.py"
SCHEDULE_FILE = REPO_ROOT / "schedule.json"
ASSIGNMENTS_FILE = REPO_ROOT / "assignments.json"
ROSTER_FILE = REPO_ROOT / "roster.json"

# Docker image names
DASHBOARD_IMAGE = "shortlist-dashboard-renderer"
API_IMAGE = "shortlist-api-renderer"
AUDIO_IMAGE = "shortlist-audio-renderer"
VIDEO_IMAGE = "shortlist-video-renderer"
WEB_IMAGE = "shortlist-web-renderer"
ADMIN_UI_IMAGE = "shortlist-admin-ui-renderer"

# Service ports
PORT_DASHBOARD = 8000
PORT_AUDIO = 8001
PORT_VIDEO = 8002
PORT_WEB = 8003
PORT_API = 8004
PORT_ADMIN = 8005

# --- Factories ---
def create_task(
    task_id: str,
    task_type: str,
    priority: int = 1,
    extra_props: Optional[Dict] = None
) -> Dict:
    """Create a task dictionary with the given properties."""
    task = {
        "id": task_id,
        "type": task_type,
        "priority": priority
    }
    if extra_props:
        task.update(extra_props)
    return task

def create_node_data(
    node_id: str,
    last_seen: Optional[datetime] = None,
    metrics: Optional[Dict] = None,
    started_at: Optional[datetime] = None
) -> Dict:
    """Create a node data dictionary."""
    if last_seen is None:
        last_seen = BASE_DATETIME
    if started_at is None:
        started_at = last_seen - timedelta(hours=1)
    
    node_data = {
        "id": node_id,
        "started_at": started_at.isoformat(),
        "last_seen": last_seen.isoformat()
    }
    
    if metrics:
        node_data["metrics"] = metrics
    
    return node_data

def create_assignment(
    task_id: str,
    node_id: str,
    task_heartbeat: Optional[datetime] = None,
    status: str = "streaming"
) -> Dict:
    """Create a task assignment dictionary."""
    if task_heartbeat is None:
        task_heartbeat = BASE_DATETIME
    
    return {
        "node_id": node_id,
        "task_heartbeat": task_heartbeat.isoformat(),
        "status": status
    }

# --- File Helpers ---
def write_json_file(file_path: Union[str, Path], data: Dict) -> None:
    """Write data to a JSON file, creating parent directories if needed."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with path.open('w') as f:
        json.dump(data, f)

def read_json_file(file_path: Union[str, Path]) -> Dict:
    """Read data from a JSON file."""
    with Path(file_path).open('r') as f:
        return json.load(f)

# --- Docker Command Helpers ---
def get_docker_build_cmd(image_name: str, context_path: str) -> List[str]:
    """Get Docker build command parts."""
    return ['docker', 'build', '-t', image_name, context_path]

def get_docker_run_cmd(
    container_name: str,
    image_name: str,
    port: int,
    volumes: Optional[List[Dict[str, str]]] = None
) -> List[str]:
    """Get Docker run command parts."""
    cmd = ['docker', 'run', '-d', '--name', container_name]
    
    # Add volume mounts
    if volumes:
        for vol in volumes:
            cmd.extend(['-v', f"{vol['source']}:{vol['target']}"])
    
    # Add port mapping
    cmd.extend(['-p', f'{port}:8000'])
    
    # Add image name
    cmd.append(image_name)
    
    return cmd

def get_docker_stop_cmd(container_id: str) -> List[str]:
    """Get Docker stop command parts."""
    return ['docker', 'stop', container_id]

def get_docker_rm_cmd(container_id: str) -> List[str]:
    """Get Docker rm command parts."""
    return ['docker', 'rm', container_id]

# --- Git Command Helpers ---
def get_git_commands(repo_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """Get common Git commands."""
    return {
        "init": ["git", "init"],
        "add": ["git", "add", "."],
        "commit": ["git", "commit", "-m"],
        "pull": ["git", "pull"],
        "push": ["git", "push"],
        "fetch": ["git", "fetch", "origin"],
        "reset": ["git", "reset", "--hard", "origin/main"],
        "config_email": ["git", "config", "user.email", "test@example.com"],
        "config_name": ["git", "config", "user.name", "Test User"]
    }