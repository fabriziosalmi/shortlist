import pytest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import time
import requests
import os
from datetime import datetime, timezone

from docker_test_utils import (
    DASHBOARD_IMAGE, API_IMAGE, AUDIO_IMAGE, VIDEO_IMAGE, WEB_IMAGE, ADMIN_UI_IMAGE,
    PORT_DASHBOARD, PORT_AUDIO, PORT_VIDEO, PORT_WEB, PORT_API, PORT_ADMIN,
    get_docker_build_cmd, get_docker_run_cmd, get_docker_stop_cmd, get_docker_rm_cmd,
    get_docker_ps_cmd, get_standard_volumes, create_mock_docker_responses
)
from test_utils import TEST_NODE_ID, create_task

# Import the Node class from node.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from node import Node, NodeState

# --- Fixtures ---
@pytest.fixture
def mock_node_id_file():
    with (patch('os.path.exists', return_value=False),
          patch('uuid.uuid4', return_value=MagicMock(hex=TEST_NODE_ID)),
          patch('builtins.open', new_callable=mock_open) as mock_file_open):
        yield mock_file_open

@pytest.fixture
def mock_git_commands():
    with (patch('node.run_command') as mock_run_command,
          patch('node.commit_and_push') as mock_commit_and_push,
          patch('node.git_pull') as mock_git_pull,
          patch('node.git_push') as mock_git_push):
        yield mock_run_command, mock_commit_and_push, mock_git_pull, mock_git_push

@pytest.fixture
def mock_json_file_operations():
    with (patch('node.read_json_file') as mock_read_json,
          patch('json.dump') as mock_json_dump,
          patch('builtins.open', new_callable=mock_open) as mock_file_open):
        yield mock_read_json, mock_json_dump, mock_file_open

# --- Test Helpers ---

def verify_docker_commands(mock_run_command, node, task_type, image_name, port, container_id):
    """Helper to verify Docker command calls."""
    volumes = get_standard_volumes()
    container_name = f'{task_type}-{node.node_id[:8]}'

    mock_run_command.assert_any_call(get_docker_build_cmd(image_name, f'renderers/{task_type}'))
    mock_run_command.assert_any_call(
        get_docker_run_cmd(container_name, image_name, port, volumes)
    )
    mock_run_command.assert_any_call(get_docker_ps_cmd(container_id))
    mock_run_command.assert_any_call(get_docker_stop_cmd(container_id), suppress_errors=True)
    mock_run_command.assert_any_call(get_docker_rm_cmd(container_id), suppress_errors=True)

# --- Helper to run a renderer in a controlled way ---
def run_renderer_in_node(node_instance, task_type, port, mock_git_commands, mock_json_file_operations):
    mock_run_command, _, _, _ = mock_git_commands
    mock_read_json, _, _ = mock_json_file_operations

    # Mock Docker commands
    mock_run_command.side_effect = [
        "container_id_123", # docker run -d ...
        "", # docker ps -q (first check, container is running)
        "", # docker ps -q (second check, container is running)
        "", # docker stop
        ""  # docker rm
    ]

    # Mock read_json_file for assignments during heartbeat
    mock_read_json.return_value = {"assignments": {task_type: {"node_id": node_instance.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node_instance.current_task = {"id": task_type, "type": task_type, "priority": 1}
    node_instance.state = NodeState.ACTIVE

    # Patch time.sleep to speed up tests, but allow a short delay for server startup
    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        # Run the active state logic in a separate thread or process if it blocks
        # For now, we'll just call it directly and mock its internal loop
        # This is a simplified approach, a real E2E would need threading
        node_instance.run_active_state()

    # Verify docker commands were called
    assert mock_run_command.call_count >= 3 # build, run, stop, rm
    verify_docker_commands(mock_run_command, node_instance, task_type, DASHBOARD_IMAGE, port, "container_id_123")

# --- Test Cases for UI/API Renderers ---

@pytest.mark.slow
def test_dashboard_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8000
    task_type = "dashboard"

    # Mock the actual docker run command to return a dummy container ID
    mock_run_command.side_effect = create_mock_docker_responses("container_id_123", running_checks=1)

    # Mock read_json_file for assignments during heartbeat
    mock_json_file_operations[0].return_value = {"assignments": {task_type: {"node_id": node.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node.current_task = {"id": task_type, "type": task_type, "priority": 1}
    node.state = NodeState.ACTIVE

    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        # Run the active state logic in a separate thread or process if it blocks
        # For now, we'll just call it directly and mock its internal loop
        # This is a simplified approach, a real E2E would need threading
        node.run_active_state()

    # Perform HTTP request
    time.sleep(2) # Give container time to start
    try:
        response = requests.get(f"http://localhost:{port}")
        assert response.status_code == 200
        assert "<title>Shortlist Dashboard</title>" in response.text or "Shortlist Dashboard" in response.text # More specific assertion
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to dashboard renderer at http://localhost:{port}: {e}")

@pytest.mark.slow
def test_api_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8004
    task_type = "api"

    # Mock the actual docker run command to return a dummy container ID
    mock_git_commands[0].side_effect = create_mock_docker_responses("container_id_api")

    # Mock read_json_file for assignments during heartbeat
    mock_json_file_operations[0].return_value = {"assignments": {task_type: {"node_id": node.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node.current_task = {"id": task_type, "type": task_type, "priority": 0}
    node.state = NodeState.ACTIVE

    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        node.run_active_state()

    # Perform HTTP request
    time.sleep(2) # Give container time to start
    try:
        response = requests.get(f"http://localhost:{port}/v1/status")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"} # More specific assertion
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to API renderer at http://localhost:{port}/v1/status: {e}")

# Add more smoke tests for other UI/API renderers (admin_ui, audio, video, web) following the same pattern

@pytest.mark.slow
def test_admin_ui_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8005
    task_type = "admin_ui"

    mock_git_commands[0].side_effect = create_mock_docker_responses("container_id_admin_ui")

    mock_json_file_operations[0].return_value = {"assignments": {task_type: {"node_id": node.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node.current_task = {"id": task_type, "type": task_type, "priority": 1}
    node.state = NodeState.ACTIVE

    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        node.run_active_state()

    time.sleep(2)
    try:
        response = requests.get(f"http://localhost:{port}")
        assert response.status_code == 200
        assert "<title>Shortlist Control Room</title>" in response.text or "Shortlist Control Room" in response.text # More specific assertion
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to admin_ui renderer at http://localhost:{port}: {e}")

@pytest.mark.slow
def test_audio_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8001
    task_type = "audio"

    mock_git_commands[0].side_effect = create_mock_docker_responses("container_id_audio")

    mock_json_file_operations[0].return_value = {"assignments": {task_type: {"node_id": node.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node.current_task = {"id": task_type, "type": task_type, "priority": 4}
    node.state = NodeState.ACTIVE

    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        node.run_active_state()

    time.sleep(2)
    try:
        response = requests.get(f"http://localhost:{port}")
        assert response.status_code == 200
        assert "<title>Shortlist Audio Stream</title>" in response.text or "Shortlist Audio Stream" in response.text # More specific assertion
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to audio renderer at http://localhost:{port}: {e}")

@pytest.mark.slow
def test_video_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8002
    task_type = "video"

    mock_git_commands[0].side_effect = create_mock_docker_responses("container_id_video")

    mock_json_file_operations[0].return_value = {"assignments": {task_type: {"node_id": node.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node.current_task = {"id": task_type, "type": task_type, "priority": 5}
    node.state = NodeState.ACTIVE

    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        node.run_active_state()

    time.sleep(2)
    try:
        response = requests.get(f"http://localhost:{port}")
        assert response.status_code == 200
        assert "<title>Shortlist Video Stream</title>" in response.text or "Shortlist Video Stream" in response.text # More specific assertion
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to video renderer at http://localhost:{port}: {e}")

@pytest.mark.slow
def test_web_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8003
    task_type = "web"

    mock_git_commands[0].side_effect = create_mock_docker_responses("container_id_web")

    mock_json_file_operations[0].return_value = {"assignments": {task_type: {"node_id": node.node_id, "task_heartbeat": datetime.now(timezone.utc).isoformat()}}}

    node.current_task = {"id": task_type, "type": task_type, "priority": 6}
    node.state = NodeState.ACTIVE

    with patch('node.time.sleep', side_effect=lambda x: time.sleep(0.1) if x > 0.1 else None):
        node.run_active_state()

    time.sleep(2)
    try:
        response = requests.get(f"http://localhost:{port}")
        assert response.status_code == 200
        assert "<title>Shortlist Web Interface</title>" in response.text or "Shortlist Web Interface" in response.text # More specific assertion
    except requests.exceptions.ConnectionError as e:
        pytest.fail(f"Could not connect to web renderer at http://localhost:{port}: {e}")

# --- Test Cases for Docker Container Startup Failures ---

@pytest.mark.slow
def test_docker_build_failure(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    mock_run_command, _, _, _ = mock_git_commands

    node = Node()
    node.current_task = create_task("task1", "dashboard", priority=1)
    node.state = NodeState.ACTIVE

    # Simulate docker build failure
    mock_run_command.side_effect = subprocess.CalledProcessError(1, "docker build", stderr="Error building image")

    with patch('node.time.sleep'): # Mock sleep to speed up test
        node.run_active_state()

    # Verify that an error was logged (implicitly by _recover_and_reset)
    # And that the state transitioned back to IDLE
    assert node.state == NodeState.IDLE
    assert node.current_task is None
    mock_run_command.assert_called_once_with(get_docker_build_cmd(DASHBOARD_IMAGE, 'renderers/dashboard'))

@pytest.mark.slow
def test_docker_run_failure(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    mock_run_command, _, _, _ = mock_git_commands

    node = Node()
    node.current_task = create_task("task1", "dashboard", priority=1)
    node.state = NodeState.ACTIVE

    # Simulate docker run failure after successful build
    mock_run_command.side_effect = [
        "build_output", # docker build success
        subprocess.CalledProcessError(1, "docker run", stderr="Error running container") # docker run failure
    ]

    with patch('node.time.sleep'): # Mock sleep to speed up test
        node.run_active_state()

    # Verify that an error was logged (implicitly by _recover_and_reset)
    # And that the state transitioned back to IDLE
    assert node.state == NodeState.IDLE
    assert node.current_task is None
    mock_run_command.assert_any_call(get_docker_build_cmd(DASHBOARD_IMAGE, 'renderers/dashboard'))
    volumes = get_standard_volumes()
    mock_run_command.assert_any_call(get_docker_run_cmd(f'task1-{node.node_id[:8]}', DASHBOARD_IMAGE, PORT_DASHBOARD, volumes))
