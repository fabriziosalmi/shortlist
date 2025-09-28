import pytest
import json
import subprocess
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as date_parse
from unittest.mock import patch, MagicMock
import os
import shutil

# Import the main functions from the renderers
# Adjust import paths as necessary based on your project structure
from renderers.governor.main import main as governor_main
from renderers.healer.main import main as healer_main

# --- Helper for Git setup ---
def init_git_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)

def commit_all(path, message):
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True)

def get_latest_commit_message(path):
    return subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=path, capture_output=True, text=True, check=True).stdout.strip()

def get_commit_count(path):
    return int(subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=path, capture_output=True, text=True, check=True).stdout.strip())

# --- Fixture for temporary Git environment ---
@pytest.fixture
def temp_git_repo(tmp_path):
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    init_git_repo(repo_path)
    yield repo_path
    # Cleanup is handled by tmp_path

# --- Test Cases for Governor ---

def test_governor_time_based_trigger(temp_git_repo):
    # Setup initial state
    schedule_data = {"tasks": []}
    triggers_data = {"triggers": {
        "test_time_trigger": {
            "condition": {"type": "time_based", "start_utc": "2025-01-01T10:00:00Z", "end_utc": "2025-01-01T11:00:00Z"},
            "actions": [
                {"type": "ADD_TASK", "id": "new_task_time", "task_type": "web", "priority": 10}
            ]
        }
    }}
    roster_data = {"nodes": []}

    (temp_git_repo / "schedule.json").write_text(json.dumps(schedule_data))
    (temp_git_repo / "triggers.json").write_text(json.dumps(triggers_data))
    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    commit_all(temp_git_repo, "Initial state for governor time test")

    # Mock datetime to be within the trigger window
    mock_now = datetime(2025, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
    with patch('renderers.governor.main.datetime') as mock_dt:
        mock_dt.utcnow.return_value = mock_now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timedelta = timedelta
        mock_dt.timezone = timezone
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)

        # Run governor main loop once (mocking sleep to prevent infinite loop)
        with patch('renderers.governor.main.time.sleep'):
            with patch('os.getcwd', return_value=str(temp_git_repo)):
                governor_main()

    # Verify schedule.json was updated
    updated_schedule = json.loads((temp_git_repo / "schedule.json").read_text())
    assert any(task["id"] == "new_task_time" for task in updated_schedule["tasks"])

    # Verify a new commit was made
    assert get_commit_count(temp_git_repo) == 2
    assert "Applied schedule changes" in get_latest_commit_message(temp_git_repo)

def test_governor_metric_based_trigger(temp_git_repo):
    # Setup initial state
    schedule_data = {"tasks": []}
    triggers_data = {"triggers": {
        "test_metric_trigger": {
            "condition": {"type": "swarm_metric_agg", "metric": "cpu_load", "aggregation": "average", "operator": "gt", "threshold": 50},
            "actions": [
                {"type": "ADD_TASK", "id": "high_cpu_task", "task_type": "text", "priority": 5}
            ]
        }
    }}
    roster_data = {"nodes": [
        {"id": "node1", "last_seen": (datetime.utcnow() - timedelta(minutes=5)).isoformat(), "metrics": {"cpu_load": 60}},
        {"id": "node2", "last_seen": (datetime.utcnow() - timedelta(minutes=5)).isoformat(), "metrics": {"cpu_load": 70}}
    ]}

    (temp_git_repo / "schedule.json").write_text(json.dumps(schedule_data))
    (temp_git_repo / "triggers.json").write_text(json.dumps(triggers_data))
    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    commit_all(temp_git_repo, "Initial state for governor metric test")

    # Run governor main loop once (mocking sleep to prevent infinite loop)
    with patch('renderers.governor.main.time.sleep'):
        with patch('os.getcwd', return_value=str(temp_git_repo)):
            governor_main()

    # Verify schedule.json was updated
    updated_schedule = json.loads((temp_git_repo / "schedule.json").read_text())
    assert any(task["id"] == "high_cpu_task" for task in updated_schedule["tasks"])

    # Verify a new commit was made
    assert get_commit_count(temp_git_repo) == 2
    assert "Applied schedule changes" in get_latest_commit_message(temp_git_repo)

# --- Test Cases for Governor (continued) ---

def test_governor_remove_task_action(temp_git_repo):
    # Setup initial state
    schedule_data = {"tasks": [{"id": "task_to_remove", "type": "web", "priority": 10}, {"id": "other_task", "type": "web", "priority": 11}]}
    triggers_data = {"triggers": {
        "test_remove_trigger": {
            "condition": {"type": "time_based", "start_utc": "2025-01-01T10:00:00Z", "end_utc": "2025-01-01T11:00:00Z"},
            "actions": [
                {"type": "REMOVE_TASK", "task_id": "task_to_remove"}
            ]
        }
    }}
    roster_data = {"nodes": []}

    (temp_git_repo / "schedule.json").write_text(json.dumps(schedule_data))
    (temp_git_repo / "triggers.json").write_text(json.dumps(triggers_data))
    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    commit_all(temp_git_repo, "Initial state for governor remove test")

    # Mock datetime to be within the trigger window
    mock_now = datetime(2025, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
    with patch('renderers.governor.main.datetime') as mock_dt:
        mock_dt.utcnow.return_value = mock_now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timedelta = timedelta
        mock_dt.timezone = timezone
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)

        # Run governor main loop once (mocking sleep to prevent infinite loop)
        with patch('renderers.governor.main.time.sleep'):
            with patch('os.getcwd', return_value=str(temp_git_repo)):
                governor_main()

    # Verify schedule.json was updated
    updated_schedule = json.loads((temp_git_repo / "schedule.json").read_text())
    assert not any(task["id"] == "task_to_remove" for task in updated_schedule["tasks"])
    assert any(task["id"] == "other_task" for task in updated_schedule["tasks"])

    # Verify a new commit was made
    assert get_commit_count(temp_git_repo) == 2
    assert "Applied schedule changes" in get_latest_commit_message(temp_git_repo)

def test_governor_swap_tasks_action(temp_git_repo):
    # Setup initial state
    schedule_data = {"tasks": [
        {"id": "task_a", "type": "web", "priority": 1},
        {"id": "task_b", "type": "web", "priority": 2}
    ]}
    triggers_data = {"triggers": {
        "test_swap_trigger": {
            "condition": {"type": "time_based", "start_utc": "2025-01-01T10:00:00Z", "end_utc": "2025-01-01T11:00:00Z"},
            "actions": [
                {"type": "SWAP_TASKS", "task_id": "task_a", "swap_with_task_id": "task_b"}
            ]
        }
    }}
    roster_data = {"nodes": []}

    (temp_git_repo / "schedule.json").write_text(json.dumps(schedule_data))
    (temp_git_repo / "triggers.json").write_text(json.dumps(triggers_data))
    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    commit_all(temp_git_repo, "Initial state for governor swap test")

    # Mock datetime to be within the trigger window
    mock_now = datetime(2025, 1, 1, 10, 30, 0, tzinfo=timezone.utc)
    with patch('renderers.governor.main.datetime') as mock_dt:
        mock_dt.utcnow.return_value = mock_now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timedelta = timedelta
        mock_dt.timezone = timezone
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)

        # Run governor main loop once (mocking sleep to prevent infinite loop)
        with patch('renderers.governor.main.time.sleep'):
            with patch('os.getcwd', return_value=str(temp_git_repo)):
                governor_main()

    # Verify schedule.json was updated and tasks are swapped
    updated_schedule = json.loads((temp_git_repo / "schedule.json").read_text())
    assert updated_schedule["tasks"][0]["id"] == "task_b"
    assert updated_schedule["tasks"][1]["id"] == "task_a"

    # Verify a new commit was made
    assert get_commit_count(temp_git_repo) == 2
    assert "Applied schedule changes" in get_latest_commit_message(temp_git_repo)



def test_healer_zombie_assignments(temp_git_repo):
    # Setup initial state
    now = datetime.utcnow()
    alive_node1_last_seen = (now - timedelta(minutes=5)).isoformat()
    alive_node2_last_seen = (now - timedelta(minutes=5)).isoformat()
    dead_node_last_seen = (now - timedelta(minutes=20)).isoformat() # Older than 15 min timeout

    roster_data = {"nodes": [
        {"id": "node1", "last_seen": alive_node1_last_seen},
        {"id": "node2", "last_seen": alive_node2_last_seen},
        {"id": "dead_node", "last_seen": dead_node_last_seen}
    ]}
    assignments_data = {"tasks": {
        "task_to_node1": {"node_id": "node1", "task_heartbeat": now.isoformat()},
        "task_to_node2": {"node_id": "node2", "task_heartbeat": now.isoformat()},
        "zombie_task": {"node_id": "dead_node", "task_heartbeat": now.isoformat()},
        "non_existent_node_task": {"node_id": "node_x", "task_heartbeat": now.isoformat()}
    }}

    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    (temp_git_repo / "assignments.json").write_text(json.dumps(assignments_data))
    commit_all(temp_git_repo, "Initial state for healer zombie test")

    # Mock datetime
    with patch('renderers.healer.main.datetime') as mock_dt:
        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timedelta = timedelta
        mock_dt.timezone = timezone
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)

        # Run healer main loop once (mocking sleep to prevent infinite loop)
        with patch('renderers.healer.main.time.sleep'):
            with patch('os.getcwd', return_value=str(temp_git_repo)):
                healer_main()

    # Verify assignments.json was updated
    updated_assignments = json.loads((temp_git_repo / "assignments.json").read_text())
    assert "zombie_task" not in updated_assignments["tasks"]
    assert "non_existent_node_task" not in updated_assignments["tasks"]
    assert "task_to_node1" in updated_assignments["tasks"]
    assert "task_to_node2" in updated_assignments["tasks"]

    # Verify a new commit was made
    assert get_commit_count(temp_git_repo) == 2
    assert "Cleared 2 zombie task assignments" in get_latest_commit_message(temp_git_repo)

def test_healer_no_anomaly(temp_git_repo):
    # Setup initial state with no anomalies
    now = datetime.utcnow()
    alive_node1_last_seen = (now - timedelta(minutes=5)).isoformat()
    alive_node2_last_seen = (now - timedelta(minutes=5)).isoformat()

    roster_data = {"nodes": [
        {"id": "node1", "last_seen": alive_node1_last_seen},
        {"id": "node2", "last_seen": alive_node2_last_seen}
    ]}
    assignments_data = {"tasks": {
        "task_to_node1": {"node_id": "node1", "task_heartbeat": now.isoformat()},
        "task_to_node2": {"node_id": "node2", "task_heartbeat": now.isoformat()}
    }}

    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    (temp_git_repo / "assignments.json").write_text(json.dumps(assignments_data))
    commit_all(temp_git_repo, "Initial state for healer no anomaly test")

    # Mock datetime
    with patch('renderers.healer.main.datetime') as mock_dt:
        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timedelta = timedelta
        mock_dt.timezone = timezone
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)

        # Run healer main loop once (mocking sleep to prevent infinite loop)
        with patch('renderers.healer.main.time.sleep'):
            with patch('os.getcwd', return_value=str(temp_git_repo)):
                healer_main()

    # Verify no new commit was made
    assert get_commit_count(temp_git_repo) == 1 # Only the initial commit
    assert "Initial state for healer no anomaly test" in get_latest_commit_message(temp_git_repo)

# --- Test Cases for Healer (continued) ---

def test_healer_stale_assignments(temp_git_repo):
    # Setup initial state
    now = datetime.utcnow()
    alive_node_last_seen = (now - timedelta(minutes=5)).isoformat()
    stale_heartbeat_time = (now - timedelta(minutes=20)).isoformat() # Older than NODE_HEARTBEAT_TIMEOUT_MINUTES (15 min)

    roster_data = {"nodes": [
        {"id": "node1", "last_seen": alive_node_last_seen}
    ]}
    assignments_data = {"tasks": {
        "active_task": {"node_id": "node1", "task_heartbeat": now.isoformat()},
        "stale_task": {"node_id": "node1", "task_heartbeat": stale_heartbeat_time}
    }}

    (temp_git_repo / "roster.json").write_text(json.dumps(roster_data))
    (temp_git_repo / "assignments.json").write_text(json.dumps(assignments_data))
    commit_all(temp_git_repo, "Initial state for healer stale test")

    # Mock datetime
    with patch('renderers.healer.main.datetime') as mock_dt:
        mock_dt.utcnow.return_value = now
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timedelta = timedelta
        mock_dt.timezone = timezone
        mock_dt.fromisoformat.side_effect = lambda x: datetime.fromisoformat(x)

        # Run healer main loop once (mocking sleep to prevent infinite loop)
        with patch('renderers.healer.main.time.sleep'):
            with patch('os.getcwd', return_value=str(temp_git_repo)):
                healer_main()

    # Verify assignments.json was updated
    updated_assignments = json.loads((temp_git_repo / "assignments.json").read_text())
    assert "stale_task" not in updated_assignments["tasks"]
    assert "active_task" in updated_assignments["tasks"]

    # Verify a new commit was made
    assert get_commit_count(temp_git_repo) == 2
    assert "Cleared 1 zombie task assignments" in get_latest_commit_message(temp_git_repo)

# --- Test Cases for Error Handling ---

def test_governor_missing_json_file(temp_git_repo):
    # Setup: only create triggers.json, but not roster.json or schedule.json
    triggers_data = {\"triggers\": {
        \"test_time_trigger\": {
            \"condition\": {\"type\": \"time_based\", \"start_utc\": \"2025-01-01T10:00:00Z\", \"end_utc\": \"2025-01-01T11:00:00Z\"},
            \"actions\": [
                {\"type\": \"ADD_TASK\", \"id\": \"new_task_time\", \"task_type\": \"web\", \"priority\": 10}
            ]
        }
    }}
    (temp_git_repo / \"triggers.json\").write_text(json.dumps(triggers_data))
    commit_all(temp_git_repo, \"Initial state for governor missing json test\")

    # Run governor main loop once (mocking sleep to prevent infinite loop)
    with patch('renderers.governor.main.time.sleep'):
        with patch('os.getcwd', return_value=str(temp_git_repo)):
            with patch('renderers.governor.main.logging.error') as mock_log_error:
                governor_main()

    # Verify an error was logged and no new commit was made
    mock_log_error.assert_called_with(\"Failed to read one or more essential JSON files. Skipping this cycle.\")
    assert get_commit_count(temp_git_repo) == 1

def test_healer_missing_json_file(temp_git_repo):
    # Setup: only create roster.json, but not assignments.json
    roster_data = {\"nodes\": [
        {\"id\": \"node1\", \"last_seen\": datetime.utcnow().isoformat()}
    ]}
    (temp_git_repo / \"roster.json\").write_text(json.dumps(roster_data))
    commit_all(temp_git_repo, \"Initial state for healer missing json test\")

    # Run healer main loop once (mocking sleep to prevent infinite loop)
    with patch('renderers.healer.main.time.sleep'):
        with patch('os.getcwd', return_value=str(temp_git_repo)):
            with patch('renderers.healer.main.logging.error') as mock_log_error:
                healer_main()

    # Verify an error was logged and no new commit was made
    mock_log_error.assert_called_with(\"Failed to read roster.json or assignments.json. Skipping this cycle.\")
    assert get_commit_count(temp_git_repo) == 1
