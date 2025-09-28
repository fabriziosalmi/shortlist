"""Docker-related test utilities and helpers."""

from typing import Dict, List, Optional
import os
from pathlib import Path

# Container names and ports
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

def get_standard_volumes(shortlist_json_path: str = "shortlist.json", output_dir: str = "./output") -> List[Dict[str, str]]:
    """Get standard volume mounts for containers."""
    return [
        {
            "source": os.path.abspath(shortlist_json_path),
            "target": "/app/data/shortlist.json:ro"
        },
        {
            "source": os.path.abspath(output_dir),
            "target": "/app/output"
        }
    ]

def get_docker_build_cmd(image_name: str, context_dir: str) -> List[str]:
    """Get Docker build command."""
    return ["docker", "build", "-t", image_name, context_dir]

def get_docker_run_cmd(
    container_name: str,
    image_name: str,
    port: int,
    volumes: Optional[List[Dict[str, str]]] = None
) -> List[str]:
    """Get Docker run command with standard options."""
    cmd = ["docker", "run", "-d", "--name", container_name]
    
    if volumes:
        for volume in volumes:
            cmd.extend(["-v", f"{volume['source']}:{volume['target']}"])
    
    cmd.extend(["-p", f"{port}:8000", image_name])
    return cmd

def get_docker_stop_cmd(container_id: str) -> List[str]:
    """Get Docker stop command."""
    return ["docker", "stop", container_id]

def get_docker_rm_cmd(container_id: str) -> List[str]:
    """Get Docker rm command."""
    return ["docker", "rm", container_id]

def get_docker_ps_cmd(container_id: str) -> List[str]:
    """Get Docker ps command to check container status."""
    return ["docker", "ps", "-q", "--filter", f"id={container_id}"]

def create_mock_docker_responses(container_id: str, *, running_checks: int = 1) -> List[str]:
    """Create a list of mock responses for Docker commands.
    
    Args:
        container_id: The container ID to use in responses
        running_checks: Number of times the container should appear to be running
    """
    responses = [
        "build_output",  # docker build
        container_id,    # docker run -d
    ]
    
    # Add running checks
    responses.extend([container_id] * running_checks)  # container is running
    responses.append("")  # container is stopped
    
    # Add cleanup responses
    responses.extend(["", ""])  # stop and rm commands
    
    return responses