import pytest
from unittest.mock import patch, mock_open, MagicMock
import json
from datetime import datetime, timedelta, timezone

# Import the Node class and other relevant functions from node.py
# Adjust the import path if node.py is not directly in the project root
from node import Node, NodeState, HEARTBEAT_INTERVAL, TASK_EXPIRATION, IDLE_PULL_INTERVAL

# --- Fixtures for common mocks ---
@pytest.fixture
def mock_node_id_file():
    with patch('os.path.exists', return_value=False),
         patch('uuid.uuid4', return_value=MagicMock(hex='test-node-id')),
         patch('builtins.open', new_callable=mock_open) as mock_file_open:
        yield mock_file_open

@pytest.fixture
def mock_git_commands():
    with patch('node.run_command') as mock_run_command,
         patch('node.commit_and_push') as mock_commit_and_push,
         patch('node.git_pull') as mock_git_pull,
         patch('node.git_push') as mock_git_push:
        yield mock_run_command, mock_commit_and_push, mock_git_pull, mock_git_push

@pytest.fixture
def mock_json_file_operations():
    with patch('node.read_json_file') as mock_read_json,
         patch('json.dump') as mock_json_dump,
         patch('builtins.open', new_callable=mock_open) as mock_file_open:
        yield mock_read_json, mock_json_dump, mock_file_open

@pytest.fixture
def mock_datetime():
    with patch('node.datetime') as mock_dt:
        mock_dt.now.return_value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timezone = timezone
        mock_dt.timedelta = timedelta
        yield mock_dt

# --- Test Cases for IDLE State Transitions ---

def test_idle_state_no_tasks_available(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.side_effect = [
        {"nodes": []}, # Initial roster read for heartbeat
        {"tasks": []}, # schedule.json
        {"assignments": {}} # assignments.json
    ]

    node = Node()
    node.last_roster_heartbeat = datetime.now(timezone.utc) # Prevent immediate heartbeat

    node.run_idle_state()

    assert node.state == NodeState.IDLE
    assert node.current_task is None
    mock_git_commands[2].assert_called_once() # git_pull should be called

def test_idle_state_free_task_found(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.side_effect = [
        {"nodes": []}, # Initial roster read for heartbeat
        {"tasks": [{"id": "task1", "type": "dashboard", "priority": 1}]}, # schedule.json
        {"assignments": {}} # assignments.json
    ]

    node = Node()
    node.last_roster_heartbeat = datetime.now(timezone.utc) # Prevent immediate heartbeat

    node.run_idle_state()

    assert node.state == NodeState.ATTEMPT_CLAIM
    assert node.current_task["id"] == "task1"
    mock_git_commands[2].assert_called_once() # git_pull should be called

def test_idle_state_orphaned_task_found(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, _, _ = mock_json_file_operations
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = now

    # Simulate an old heartbeat
    old_heartbeat_time = (now - TASK_EXPIRATION - timedelta(seconds=1)).isoformat()

    mock_read_json.side_effect = [
        {"nodes": []}, # Initial roster read for heartbeat
        {"tasks": [{"id": "task1", "type": "dashboard", "priority": 1}]}, # schedule.json
        {"assignments": {"task1": {"node_id": "some_node", "task_heartbeat": old_heartbeat_time}}} # assignments.json
    ]

    node = Node()
    node.last_roster_heartbeat = now # Prevent immediate heartbeat

    node.run_idle_state()

    assert node.state == NodeState.ATTEMPT_CLAIM
    assert node.current_task["id"] == "task1"
    mock_git_commands[2].assert_called_once() # git_pull should be called

# --- Test Cases for ATTEMPT_CLAIM State Logic ---

def test_attempt_claim_success(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, mock_json_dump, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    mock_read_json.return_value = {"assignments": {}} # assignments.json before claim
    mock_commit_and_push.return_value = True # Simulate successful commit and push

    node = Node()
    node.current_task = {"id": "task1", "type": "dashboard", "priority": 1}
    node.state = NodeState.ATTEMPT_CLAIM

    # Mock random.randint to avoid actual sleep during jitter
    with patch('random.randint', return_value=0):
        node.run_attempt_claim_state()

    assert node.state == NodeState.ACTIVE
    mock_git_pull.assert_called_once() # git_pull before recheck
    mock_json_dump.assert_called_once() # assignments.json written
    mock_commit_and_push.assert_called_once_with(['assignments.json'], f'feat(assignments): node {node.node_id[:8]} claims task1')

def test_attempt_claim_failure_conflict(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, mock_json_dump, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    mock_read_json.return_value = {"assignments": {}} # assignments.json before claim
    mock_commit_and_push.return_value = False # Simulate failed commit and push

    node = Node()
    node.current_task = {"id": "task1", "type": "dashboard", "priority": 1}
    node.state = NodeState.ATTEMPT_CLAIM

    with patch('random.randint', return_value=0):
        node.run_attempt_claim_state()

    assert node.state == NodeState.IDLE
    mock_git_pull.assert_called_once() # git_pull before recheck
    mock_json_dump.assert_called_once() # assignments.json written
    mock_commit_and_push.assert_called_once() # Attempted commit and push

def test_attempt_claim_task_stolen(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, _, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = now

    # Simulate task already claimed by another node with a fresh heartbeat
    fresh_heartbeat_time = (now - timedelta(seconds=10)).isoformat()
    mock_read_json.return_value = {"assignments": {"task1": {"node_id": "another_node", "task_heartbeat": fresh_heartbeat_time}}} # assignments.json after jitter

    node = Node()
    node.current_task = {"id": "task1", "type": "dashboard", "priority": 1}
    node.state = NodeState.ATTEMPT_CLAIM

    with patch('random.randint', return_value=0):
        node.run_attempt_claim_state()

    assert node.state == NodeState.IDLE
    mock_git_pull.assert_called_once() # git_pull before recheck
    mock_commit_and_push.assert_not_called() # No commit if task stolen

# --- Test Cases for Helper Functions (Example: read_json_file) ---

def test_read_json_file_success(mock_json_file_operations):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.return_value = {"key": "value"}
    
    result = Node.read_json_file("some_file.json")
    assert result == {"key": "value"}

def test_read_json_file_not_found(mock_json_file_operations):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.side_effect = FileNotFoundError

    result = Node.read_json_file("non_existent_file.json")
    assert result is None

def test_read_json_file_decode_error(mock_json_file_operations):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    result = Node.read_json_file("malformed.json")
    assert result is None
