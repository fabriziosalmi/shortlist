import pytest
from unittest.mock import patch, MagicMock
import subprocess
import time
import requests
import os
import json

# Import the Node class from node.py
from node import Node, NodeState

# --- Fixtures ---
@pytest.fixture
def mock_node_id_file():
    with (patch('os.path.exists', return_value=False),
          patch('uuid.uuid4', return_value=MagicMock(hex='test-node-id')),
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
    assert any('docker build' in call[0][0] for call in mock_run_command.call_args_list)
    assert any('docker run' in call[0][0] and f'-p {port}:8000' in call[0][0] for call in mock_run_command.call_args_list)
    assert any('docker stop' in call[0][0] for call in mock_run_command.call_args_list)
    assert any('docker rm' in call[0][0] for call in mock_run_command.call_args_list)

# --- Test Cases for UI/API Renderers ---

@pytest.mark.slow
def test_dashboard_renderer_smoke_test(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    node = Node()
    port = 8000
    task_type = "dashboard"

    # Mock the actual docker run command to return a dummy container ID
    mock_git_commands[0].side_effect = [
        "build_output", # docker build
        "container_id_dashboard", # docker run -d
        "container_id_dashboard", # docker ps -q (container is running)
        "", # docker ps -q (container is running)
        "", # docker stop
        ""  # docker rm
    ]

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
    mock_git_commands[0].side_effect = [
        "build_output", # docker build
        "container_id_api", # docker run -d
        "container_id_api", # docker ps -q (container is running)
        "", # docker ps -q (container is running)
        "", # docker stop
        ""  # docker rm
    ]

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

    mock_git_commands[0].side_effect = [
        "build_output", # docker build
        "container_id_admin_ui", # docker run -d
        "container_id_admin_ui", # docker ps -q (container is running)
        "", # docker ps -q (container is running)
        "", # docker stop
        ""  # docker rm
    ]

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

    mock_git_commands[0].side_effect = [
        "build_output", # docker build
        "container_id_audio", # docker run -d
        "container_id_audio", # docker ps -q (container is running)
        "", # docker ps -q (container is running)
        "", # docker stop
        ""  # docker rm
    ]

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

    mock_git_commands[0].side_effect = [
        "build_output", # docker build
        "container_id_video", # docker run -d
        "container_id_video", # docker ps -q (container is running)
        "", # docker ps -q (container is running)
        "", # docker stop
        ""  # docker rm
    ]

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

    mock_git_commands[0].side_effect = [
        "build_output", # docker build
        "container_id_web", # docker run -d
        "container_id_web", # docker ps -q (container is running)
        "", # docker ps -q (container is running)
        "", # docker stop
        ""  # docker rm
    ]

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
    node.current_task = {\"id\": \"task1\", \"type\": \"dashboard\", \"priority\": 1}
    node.state = NodeState.ACTIVE

    # Simulate docker build failure
    mock_run_command.side_effect = subprocess.CalledProcessError(1, \"docker build\", stderr=\"Error building image\")

    with patch('node.time.sleep'): # Mock sleep to speed up test
        node.run_active_state()

    # Verify that an error was logged (implicitly by _recover_and_reset)
    # And that the state transitioned back to IDLE
    assert node.state == NodeState.IDLE
    assert node.current_task is None
    mock_run_command.assert_called_once_with([\'docker\', \'build\', \'-t\', \'shortlist-dashboard-renderer\', \'renderers/dashboard\'])

@pytest.mark.slow
def test_docker_run_failure(mock_node_id_file, mock_git_commands, mock_json_file_operations):
    mock_run_command, _, _, _ = mock_git_commands

    node = Node()
    node.current_task = {\"id\": \"task1\", \"type\": \"dashboard\", \"priority\": 1}
    node.state = NodeState.ACTIVE

    # Simulate docker run failure after successful build
    mock_run_command.side_effect = [
        \"build_output\", # docker build success
        subprocess.CalledProcessError(1, \"docker run\", stderr=\"Error running container\") # docker run failure
    ]

    with patch('node.time.sleep'): # Mock sleep to speed up test
        node.run_active_state()

    # Verify that an error was logged (implicitly by _recover_and_reset)
    # And that the state transitioned back to IDLE
    assert node.state == NodeState.IDLE
    assert node.current_task is None
    mock_run_command.assert_any_call([\'docker\', \'build\', \'-t\', \'shortlist-dashboard-renderer\', \'renderers/dashboard\'])
    mock_run_command.assert_any_call([\'docker\', \'run\', \'-d\', \'--name\', f\'task1-{node.node_id[:8]}\', \'-v\', f\'{os.path.abspath(\"shortlist.json\")}:/app/data/shortlist.json:ro\', \'-v\', f\'{os.path.abspath(\"./output\")}:/app/output\', \'-p\', \'8000:8000\', \'shortlist-dashboard-renderer\'])
