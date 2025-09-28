import pytest
import json
import subprocess
import time
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import os
from pathlib import Path

# Import the Node class from node.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from node import Node, NodeState, ROSTER_FILE, ASSIGNMENTS_FILE, SCHEDULE_FILE

# --- Helper for Git setup ---
def init_git_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)

def commit_all(path, message):
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True)

def get_commit_messages(path):
    return subprocess.run(["git", "log", "--pretty=%B"], cwd=path, capture_output=True, text=True, check=True).stdout.strip().split('\n')

# --- Fixture for temporary Git environment ---
@pytest.fixture
def temp_e2e_repo(tmp_path):
    repo_path = tmp_path / "e2e_repo"
    repo_path.mkdir()
    init_git_repo(repo_path)

    # Create initial empty files
    (repo_path / ROSTER_FILE).write_text(json.dumps({"nodes": []}))
    (repo_path / ASSIGNMENTS_FILE).write_text(json.dumps({"assignments": {}}))
    (repo_path / SCHEDULE_FILE).write_text(json.dumps({"tasks": []}))
    commit_all(repo_path, "Initial empty state")

    yield repo_path

# --- Test Case for E2E Lifecycle ---
def test_e2e_claim_and_run_multiple_tasks_cycle(temp_e2e_repo):
    # Setup: Create a schedule with multiple tasks
    schedule_data = {"tasks": [
        {"id": "e2e_task_1", "type": "dashboard", "priority": 1},
        {"id": "e2e_task_2", "type": "audio", "priority": 2},
        {"id": "e2e_task_3", "type": "web", "priority": 3}
    ]}
    (temp_e2e_repo / SCHEDULE_FILE).write_text(json.dumps(schedule_data))
    commit_all(temp_e2e_repo, "Add multiple e2e test tasks to schedule")

    # Mock external dependencies for the Node
    with patch('node.run_command') as mock_run_command,\
         patch('node.commit_and_push') as mock_commit_and_push,\
         patch('node.git_pull') as mock_git_pull,\
         patch('node.git_push') as mock_git_push,\
         patch('node.read_json_file') as mock_read_json_file,\
         patch('node.datetime') as mock_dt,\
         patch('time.sleep') as mock_sleep: # Speed up all sleeps

        # Configure mocks
        mock_dt.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timezone = timezone
        mock_dt.timedelta = timedelta

        # Mock git commands to operate on the temp_e2e_repo
        def mock_run_command_impl(command, cwd=None, **kwargs):
            if cwd is None: cwd = temp_e2e_repo
            return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True, **kwargs).stdout.strip()

        # Create a more sophisticated mock for run_command that handles Docker commands dynamically
        docker_containers = {}
        heartbeat_counts = {}
        max_task_heartbeats = 3  # Stop container after this many heartbeats

        def handle_docker_command(command, **kwargs):
            if 'docker' not in command[0]:
                return mock_run_command_impl(command, **kwargs)
            if command[1] == 'build':
                return "build_output"
            elif command[1] == 'run':
                # Extract task ID from the container name argument (should be after --name)
                name_idx = command.index('--name')
                if name_idx + 1 < len(command):
                    # Example name: 'e2e_task_1-e2e-test'
                    container_name = command[name_idx + 1]
                    task_id = container_name.split('-')[0]  # Get just e2e_task_1 part
                else:
                    task_id = next(arg for arg in command if 'e2e_task' in arg)
                
                # Use the full task ID as part of container ID
                container_id = f"container_id_{task_id}"
                docker_containers[container_id] = True
                heartbeat_counts[container_id] = 0
                return container_id
            elif command[1] == 'ps':
                # For 'ps' commands that check container status
                if '--filter' in command:
                    # Format expected is: --filter id=container_id
                    filter_idx = command.index('--filter')
                    if filter_idx + 1 < len(command):
                        container_id = command[filter_idx + 1].split('=')[-1]
                        if docker_containers.get(container_id):
                            heartbeat_counts[container_id] = heartbeat_counts.get(container_id, 0) + 1
                            # Simulate container exit after N heartbeats
                            if heartbeat_counts[container_id] >= max_task_heartbeats:
                                docker_containers[container_id] = False
                                return ""
                            # Return running container ID (that's what Docker ps -q returns)
                            return container_id
                    return ""
                return ""
            elif command[1] == 'stop':
                container_id = command[-1]
                docker_containers[container_id] = False
                return ""
            elif command[1] == 'rm':
                return ""
            return ""

        mock_run_command.side_effect = handle_docker_command

        def mock_commit_and_push_impl(files, message):
            # Convert relative paths to absolute
            abs_files = [os.path.join(temp_e2e_repo, f) if not os.path.isabs(f) else f for f in files]
            # Simulate git add, commit, push on the temp repo
            subprocess.run(["git", "add"] + abs_files, cwd=temp_e2e_repo, check=True)
            status_result = subprocess.run(["git", "status", "--porcelain"], cwd=temp_e2e_repo, capture_output=True, text=True, check=True).stdout.strip()
            # Check if any of the files appear in status (accounting for relative vs absolute paths)
            changed = False
            for file in files:
                abs_path = os.path.join(temp_e2e_repo, file) if not os.path.isabs(file) else file
                rel_path = os.path.relpath(abs_path, temp_e2e_repo)
                if rel_path in status_result:
                    changed = True
                    break
            if changed:
                subprocess.run(["git", "commit", "-m", message], cwd=temp_e2e_repo, check=True)
                # No actual push needed for local repo test, but simulate success
                return True
            return False
        mock_commit_and_push.side_effect = mock_commit_and_push_impl

        def mock_git_pull_impl():
            # Simulate a successful git pull without actually pulling from a remote
            pass
        mock_git_pull.side_effect = mock_git_pull_impl

        def mock_git_push_impl():
            # No actual push needed for local repo test, but simulate success
            pass
        mock_git_push.side_effect = mock_git_push_impl

        # Mock read_json_file to read from the temp_e2e_repo
        def mock_read_json_file_impl(filepath):
            full_path = temp_e2e_repo / filepath
            if full_path.exists():
                with full_path.open('r') as f:
                    return json.load(f)
            return None
        mock_read_json_file.side_effect = mock_read_json_file_impl

        # Instantiate the Node, configured to use the temporary repo
        with patch('os.getcwd', return_value=str(temp_e2e_repo)):
            node = Node()
            node.node_id = "e2e-test-node"
            node_id_file = temp_e2e_repo / f".node_id_{os.getpid()}"
            node_id_file.write_text(node.node_id)

            # Run the node's main loop in a separate thread
            stop_event = threading.Event()
            def run_node_target():
                # We need to ensure the node runs enough cycles to claim all tasks
                # and perform a few heartbeats for each
                for _ in range(30): # Run for a fixed number of cycles
                    if stop_event.is_set():
                        break
                    try:
                        node.run()
                    except Exception as e:
                        print(f"Node thread error: {e}")
                        break
                    time.sleep(0.1) # Small sleep to allow other mocks to work
            
            node_thread = threading.Thread(target=run_node_target)
            node_thread.daemon = True # Allow main program to exit even if thread is still running
            node_thread.start()

            # Run for a fixed number of iterations instead of time-based waiting
            iterations = 0
            max_iterations = 50  # Increased from 10 to give more time for all tasks
            while iterations < max_iterations:
                iterations += 1
                time.sleep(0.1)
                
                # Check if we have all the expected commits
                commit_messages = get_commit_messages(temp_e2e_repo)
                if all(f"feat(assignments): node {node.node_id[:8]} claims {task_id}" in ' '.join(commit_messages)
                       for task_id in ["e2e_task_1", "e2e_task_2", "e2e_task_3"]):
                    break
            
            stop_event.set()
            node_thread.join(timeout=1)  # Reduced timeout since we're not actually sleeping

            # Verifications
            commit_messages = get_commit_messages(temp_e2e_repo)
            print(f"E2E Commit messages: {commit_messages}")

            # Check for node registration commit
            assert any(f"chore(roster): heartbeat from node {node.node_id[:8]}" in msg for msg in commit_messages)

            # Check for task claim commits for all tasks
            for task_id in ["e2e_task_1", "e2e_task_2", "e2e_task_3"]:
                assert any(f"feat(assignments): node {node.node_id[:8]} claims {task_id}" in msg for msg in commit_messages)

            # Check for at least one task heartbeat commit for each task
            for task_id in ["e2e_task_1", "e2e_task_2", "e2e_task_3"]:
                assert any(f"chore(assignments): task heartbeat for {task_id} from node {node.node_id[:8]}" in msg for msg in commit_messages)

            # Verify final state of assignments.json (all tasks should be assigned to this node)
            final_assignments = json.loads((temp_e2e_repo / ASSIGNMENTS_FILE).read_text())
            assert "assignments" in final_assignments
            for task_id in ["e2e_task_1", "e2e_task_2", "e2e_task_3"]:
                assert task_id in final_assignments["assignments"]
                assert final_assignments["assignments"][task_id]["node_id"] == node.node_id