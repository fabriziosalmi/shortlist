import pytest
import json
import subprocess
import time
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import os

# Import the Node class from node.py
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
@pytest. इसकी एक कॉपी है
pytest.fixture
def temp_e2e_repo(tmp_path):
    repo_path = tmp_path / "e2e_repo"
    repo_path.mkdir()
    init_git_repo(repo_path)

    # Create initial empty files
    (repo_path / ROSTER_FILE).write_text(json.dumps({"nodes": []}))
    (repo_path / ASSIGNMENTS_FILE).write_text(json.dumps({"tasks": {}}))
    (repo_path / SCHEDULE_FILE).write_text(json.dumps({"tasks": []}))
    commit_all(repo_path, "Initial empty state")

    yield repo_path

# --- Test Case for E2E Lifecycle ---

def test_e2e_claim_and_run_cycle(temp_e2e_repo):
    # Setup: Create a schedule with one task
    schedule_data = {"tasks": [
        {"id": "e2e_test_task", "type": "dashboard", "priority": 1}
    ]}
    (temp_e2e_repo / SCHEDULE_FILE).write_text(json.dumps(schedule_data))
    commit_all(temp_e2e_repo, "Add e2e test task to schedule")

    # Mock external dependencies for the Node
    with patch('node.run_command') as mock_run_command,
         patch('node.commit_and_push') as mock_commit_and_push,
         patch('node.git_pull') as mock_git_pull,
         patch('node.git_push') as mock_git_push,
         patch('node.read_json_file') as mock_read_json_file,
         patch('node.json.dump') as mock_json_dump,
         patch('builtins.open', new_callable=MagicMock) as mock_open_file,
         patch('node.datetime') as mock_dt,
         patch('node.time.sleep', side_effect=lambda x: None): # Speed up sleeps

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
        mock_run_command.side_effect = mock_run_command_impl

        def mock_commit_and_push_impl(files, message):
            # Simulate git add, commit, push on the temp repo
            subprocess.run(["git", "add"] + files, cwd=temp_e2e_repo, check=True)
            status_result = subprocess.run(["git", "status", "--porcelain"], cwd=temp_e2e_repo, capture_output=True, text=True, check=True).stdout.strip()
            if any(file in status_result for file in files):
                subprocess.run(["git", "commit", "-m", message], cwd=temp_e2e_repo, check=True)
                # No actual push needed for local repo test, but simulate success
                return True
            return False
        mock_commit_and_push.side_effect = mock_commit_and_push_impl

        def mock_git_pull_impl():
            subprocess.run(["git", "pull"], cwd=temp_e2e_repo, check=True)
        mock_git_pull.side_effect = mock_git_pull_impl

        def mock_git_push_impl():
            # No actual push needed for local repo test, but simulate success
            pass
        mock_git_push.side_effect = mock_git_push_impl

        # Mock read_json_file to read from the temp_e2e_repo
        def mock_read_json_file_impl(filepath):
            full_path = temp_e2e_repo / filepath
            if full_path.exists():
                with open(full_path, 'r') as f:
                    return json.load(f)
            return None
        mock_read_json_file.side_effect = mock_read_json_file_impl

        # Mock json.dump to write to the temp_e2e_repo
        def mock_json_dump_impl(data, fp, **kwargs):
            # Get the file path from the mock_open_file object
            file_path = fp.name
            with open(file_path, 'w') as f:
                json.dump(data, f, **kwargs)
        mock_json_dump.side_effect = mock_json_dump_impl

        # Mock Docker container operations (start/stop/is_running)
        # Simulate a container that starts and stays running
        mock_run_command.side_effect = [
            "build_output", # docker build
            "container_id_e2e", # docker run -d
            "container_id_e2e", # docker ps -q (first check, container is running)
            "container_id_e2e", # docker ps -q (second check, container is running)
            "", # docker stop
            ""  # docker rm
        ] * 10 # Repeat to allow multiple heartbeats

        # Instantiate the Node, configured to use the temporary repo
        # We need to ensure the Node's internal GIT_REPO_PATH is set correctly
        # This is tricky as GIT_REPO_PATH is a global in node.py
        # For this E2E, we'll assume the test runner's CWD is temp_e2e_repo
        # Or, we can patch os.getcwd
        with patch('os.getcwd', return_value=str(temp_e2e_repo)):
            node = Node()
            node.node_id = "e2e-test-node"
            (temp_e2e_repo / ".node_id_" + str(os.getpid())).write_text(node.node_id)

            # Run the node's main loop in a separate thread
            stop_event = threading.Event()
            def run_node_target():
                while not stop_event.is_set():
                    try:
                        node.run()
                    except Exception as e:
                        print(f"Node thread error: {e}")
                        break
            
            node_thread = threading.Thread(target=run_node_target)
            node_thread.daemon = True # Allow main program to exit even if thread is still running
            node_thread.start()

            # Let the node run for a limited time
            time.sleep(10) # Allow enough time for multiple cycles
            stop_event.set()
            node_thread.join(timeout=5) # Wait for thread to finish, with a timeout

            # Verifications
            commit_messages = get_commit_messages(temp_e2e_repo)
            print(f"E2E Commit messages: {commit_messages}")

            # Check for node registration commit
            assert any(f"chore(roster): heartbeat from node {node.node_id[:8]}" in msg for msg in commit_messages)

            # Check for task claim commit
            assert any(f"feat(assignments): node {node.node_id[:8]} claims e2e_test_task" in msg for msg in commit_messages)

            # Check for at least one task heartbeat commit
            assert any(f"chore(assignments): task heartbeat for e2e_test_task from node {node.node_id[:8]}" in msg for msg in commit_messages)

            # Verify final state of assignments.json (task should be assigned to this node)
            final_assignments = json.loads((temp_e2e_repo / ASSIGNMENTS_FILE).read_text())
            assert final_assignments["tasks"]["e2e_test_task"]["node_id"] == node.node_id
