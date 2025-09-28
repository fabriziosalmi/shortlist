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
    mock_read_json.return_value = {\"key\": \"value\"}
    
    result = Node.read_json_file(\"some_file.json\")
    assert result == {\"key\": \"value\"}

def test_read_json_file_not_found(mock_json_file_operations):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.side_effect = FileNotFoundError

    result = Node.read_json_file(\"non_existent_file.json\")
    assert result is None

def test_read_json_file_decode_error(mock_json_file_operations):
    mock_read_json, _, _ = mock_json_file_operations
    mock_read_json.side_effect = json.JSONDecodeError(\"Expecting value\", \"\", 0)

    result = Node.read_json_file(\"malformed.json\")
    assert result is None

# --- Test Cases for perform_roster_heartbeat ---

def test_perform_roster_heartbeat_new_node(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, mock_json_dump, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    # Simulate roster.json not containing this node initially
    mock_read_json.side_effect = [
        {\"nodes\": []}, # Initial read for roster heartbeat
        {\"nodes\": []}  # read_json_file for ROSTER_FILE
    ]

    node = Node()
    node.node_id = \"test-node-id\" # Ensure consistent node_id for assertions

    with patch(\'psutil.cpu_percent\', return_value=10.0),\
         patch(\'psutil.virtual_memory\', return_value=MagicMock(percent=20.0)):
        node.perform_roster_heartbeat()

    # Verify roster.json was read and written
    mock_read_json.assert_called_with(ROSTER_FILE)
    mock_json_dump.assert_called_once()

    # Verify commit_and_push was called with correct message
    mock_commit_and_push.assert_called_once_with([ROSTER_FILE], f\'chore(roster): heartbeat from node {node.node_id[:8]}\')

    # Verify the content written to roster.json (mock_json_dump\'s first arg)
    written_roster = mock_json_dump.call_args[0][0]
    assert len(written_roster[\"nodes\"]) == 1
    assert written_roster[\"nodes\"][0][\"id\"] == node.node_id
    assert \"last_seen\" in written_roster[\"nodes\"][0]
    assert written_roster[\"nodes\"][0][\"metrics\"][\"cpu_load\"] == 10.0
    assert written_roster[\"nodes\"][0][\"metrics\"][\"memory_percent\"] == 20.0

def test_perform_roster_heartbeat_existing_node(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, mock_json_dump, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    # Simulate roster.json containing this node
    initial_roster = {\"nodes\": [{\"id\": \"test-node-id\", \"started_at\": \"2025-01-01T10:00:00+00:00\", \"last_seen\": \"2025-01-01T11:00:00+00:00\", \"metrics\": {\"cpu_load\": 5.0, \"memory_percent\": 10.0}}]}
    mock_read_json.side_effect = [
        {\"nodes\": []}, # Initial read for roster heartbeat
        initial_roster # read_json_file for ROSTER_FILE
    ]

    node = Node()
    node.node_id = \"test-node-id\"

    with patch(\'psutil.cpu_percent\', return_value=15.0),\
         patch(\'psutil.virtual_memory\', return_value=MagicMock(percent=25.0)):
        node.perform_roster_heartbeat()

    # Verify roster.json was read and written
    mock_read_json.assert_called_with(ROSTER_FILE)
    mock_json_dump.assert_called_once()

    # Verify commit_and_push was called with correct message
    mock_commit_and_push.assert_called_once_with([ROSTER_FILE], f\'chore(roster): heartbeat from node {node.node_id[:8]}\')

    # Verify the content written to roster.json (mock_json_dump\'s first arg)
    written_roster = mock_json_dump.call_args[0][0]
    assert len(written_roster[\"nodes\"]) == 1
    assert written_roster[\"nodes\"][0][\"id\"] == node.node_id
    assert written_roster[\"nodes\"][0][\"metrics\"][\"cpu_load\"] == 15.0
    assert written_roster[\"nodes\"][0][\"metrics\"][\"memory_percent\"] == 25.0
    assert written_roster[\"nodes\"][0][\"last_seen\"] > initial_roster[\"nodes\"][0][\"last_seen\"] # last_seen should be updated

# --- Test Cases for _recover_and_reset ---
def test_recover_and_reset_git_error(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_run_command, _, _, _ = mock_git_commands

    node = Node()
    node.state = NodeState.ACTIVE
    node.current_task = {\"id\": \"task1\", \"type\": \"dashboard\", \"priority\": 1}

    # Simulate a git error
    mock_run_command.side_effect = subprocess.CalledProcessError(1, \"git pull\", stderr=\"fatal: unable to access \'...\': some error\")

    with patch('node.time.sleep'): # Mock sleep to speed up test
        node._recover_and_reset(\"Git operation\")

    # Verify git commands for reset were called
    mock_run_command.assert_any_call([\'git\', \'fetch\', \'origin\'])
    mock_run_command.assert_any_call([\'git\', \'reset\', \'--hard\', \'origin/main\']) # Assuming \'main\' branch

    # Verify state reset
    assert node.state == NodeState.IDLE
    assert node.current_task is None

# --- Test Cases for ACTIVE State Logic ---
def test_active_state_task_heartbeat_and_release(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, mock_json_dump, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    node = Node()
    node.node_id = \"test-node-id\"
    node.current_task = {\"id\": \"task1\", \"type\": \"dashboard\", \"priority\": 1}
    node.state = NodeState.ACTIVE

    # Mock Docker commands: build, run, ps (running), ps (stopped), stop, rm
    mock_run_command.side_effect = [
        \"build_output\", # docker build
        \"container_id_123\", # docker run -d
        \"container_id_123\", # docker ps -q (first check, container is running)
        \"\", # docker ps -q (second check, container is stopped, to break the loop)
        \"\", # docker stop
        \"\"  # docker rm
    ]

    # Mock read_json_file for assignments during heartbeat
    # Simulate that the assignment is still ours for the first heartbeat, then it\'s lost
    initial_assignments = {\"assignments\": {\"task1\": {\"node_id\": node.node_id, \"task_heartbeat\": (mock_datetime.now.return_value - timedelta(seconds=30)).isoformat()}}}
    mock_read_json.side_effect = [
        initial_assignments, # First read for heartbeat (assignment is ours)
        {\"assignments\": {}} # Second read for heartbeat (assignment is lost)
    ]

    # Mock time.sleep to control the loop iterations
    with patch('node.time.sleep', side_effect=[0.1, 0.1, 0.1]): # Allow a few sleeps
        node.run_active_state()

    # Verify Docker commands
    mock_run_command.assert_any_call([\'docker\', \'build\', \'-t\', \'shortlist-dashboard-renderer\', \'renderers/dashboard\'])
    mock_run_command.assert_any_call([\'docker\', \'run\', \'-d\', \'--name\', f\'task1-{node.node_id[:8]}\', \'-v\', f\'{os.path.abspath(\"shortlist.json\")}:/app/data/shortlist.json:ro\', \'-v\', f\'{os.path.abspath(\"./output\")}:/app/output\', \'-p\', \'8000:8000\', \'shortlist-dashboard-renderer\'])
    mock_run_command.assert_any_call([\'docker\', \'ps\', \'-q\', \'--filter\', \'id=container_id_123\'])
    mock_run_command.assert_any_call([\'docker\', \'stop\', \'container_id_123\'], suppress_errors=True)
    mock_run_command.assert_any_call([\'docker\', \'rm\', \'container_id_123\'], suppress_errors=True)

    # Verify heartbeat update and commit
    assert mock_json_dump.call_count >= 1 # At least one dump for heartbeat
    assert mock_commit_and_push.call_count >= 1 # At least one commit for heartbeat

    # Verify state transition
    assert node.state == NodeState.IDLE
    assert node.current_task is None

def test_active_state_lost_assignment(mock_node_id_file, mock_git_commands, mock_json_file_operations, mock_datetime):
    mock_read_json, mock_json_dump, _ = mock_json_file_operations
    mock_run_command, mock_commit_and_push, mock_git_pull, _ = mock_git_commands

    node = Node()
    node.node_id = \"test-node-id\"
    node.current_task = {\"id\": \"task1\", \"type\": \"dashboard\", \"priority\": 1}
    node.state = NodeState.ACTIVE

    # Mock Docker commands: build, run, ps (running), stop, rm
    mock_run_command.side_effect = [
        \"build_output\", # docker build
        \"container_id_123\", # docker run -d
        \"container_id_123\", # docker ps -q (container is running)
        \"\", # docker stop
        \"\"  # docker rm
    ]

    # Simulate that the assignment is lost immediately after starting
    mock_read_json.side_effect = [
        {\"assignments\": {\"task1\": {\"node_id\": node.node_id, \"task_heartbeat\": (mock_datetime.now.return_value - timedelta(seconds=30)).isoformat()}}}, # First read for heartbeat (assignment is ours)
        {\"assignments\": {\"task1\": {\"node_id\": \"another_node\", \"task_heartbeat\": (mock_datetime.now.return_value - timedelta(seconds=10)).isoformat()}}} # Second read, assignment lost
    ]

    with patch('node.time.sleep', side_effect=[0.1, 0.1]): # Allow a few sleeps
        node.run_active_state()

    # Verify Docker container was stopped and removed
    mock_run_command.assert_any_call([\'docker\', \'stop\', \'container_id_123\'], suppress_errors=True)
    mock_run_command.assert_any_call([\'docker\', \'rm\', \'container_id_123\'], suppress_errors=True)

    # Verify state transition
    assert node.state == NodeState.IDLE
    assert node.current_task is None
