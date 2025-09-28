import subprocess
import time
import requests
import json
import os

# --- Test Configuration ---
NODE_PY = "node.py"
SCHEDULE_FILE = "schedule.json"
ASSIGNMENTS_FILE = "assignments.json"
ROSTER_FILE = "roster.json"

# --- Helper Functions ---
def cleanup():
    subprocess.run(["pkill", "-f", "node.py"], check=False)
    container_ids = subprocess.check_output(["docker", "ps", "-aq"]).decode("utf-8").split()
    if container_ids:
        subprocess.run(["docker", "stop"] + container_ids, check=False)
        subprocess.run(["docker", "rm"] + container_ids, check=False)
    with open(ASSIGNMENTS_FILE, "w") as f:
        json.dump({}, f)
    with open(ROSTER_FILE, "w") as f:
        json.dump({}, f)

def start_node():
    return subprocess.Popen(["python3", NODE_PY])

def wait_for_task(task_id, timeout=60):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with open(ASSIGNMENTS_FILE, "r") as f:
                assignments = json.load(f)
            if task_id in assignments.get("assignments", {}) and assignments["assignments"][task_id]["status"] == "streaming":
                return True
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(1)
    return False

# --- Tests ---

def test_dashboard_renderer():
    cleanup()
    with open(SCHEDULE_FILE, "w") as f:
        json.dump({"tasks": [{"id": "swarm_status_dashboard", "type": "dashboard", "priority": 0}]}, f)
    
    node_process = start_node()
    assert wait_for_task("swarm_status_dashboard"), "Dashboard renderer did not start in time."
    
    try:
        response = requests.get("http://localhost:8000")
        assert response.status_code == 200
        assert "Swarm Dashboard" in response.text
    finally:
        node_process.kill()
        cleanup()

def test_audio_renderer():
    cleanup()
    with open(SCHEDULE_FILE, "w") as f:
        json.dump({"tasks": [{"id": "self_hosted_audio_stream", "type": "audio", "priority": 0}]}, f)
    
    node_process = start_node()
    assert wait_for_task("self_hosted_audio_stream"), "Audio renderer did not start in time."
    
    try:
        response = requests.get("http://localhost:8001")
        assert response.status_code == 200
    finally:
        node_process.kill()
        cleanup()

def test_text_renderer():
    cleanup()
    with open(SCHEDULE_FILE, "w") as f:
        json.dump({"tasks": [{"id": "telegram_text_posts", "type": "text", "priority": 0}]}, f)
    
    node_process = start_node()
    assert wait_for_task("telegram_text_posts"), "Text renderer did not start in time."
    
    # The text renderer does not expose a port, so we just check if it starts.
    # A more advanced test could check the output of the container.
    node_process.kill()
    cleanup()

def test_api_renderer():
    cleanup()
    with open(SCHEDULE_FILE, "w") as f:
        json.dump({"tasks": [{"id": "shortlist_api", "type": "api", "priority": 0}]}, f)
    
    node_process = start_node()
    assert wait_for_task("shortlist_api"), "API renderer did not start in time."
    
    try:
        response = requests.get("http://localhost:8002/api/shortlist")
        assert response.status_code == 200
        assert "items" in response.json()
    finally:
        node_process.kill()
        cleanup()

def test_web_renderer():
    cleanup()
    with open(SCHEDULE_FILE, "w") as f:
        json.dump({"tasks": [{"id": "shortlist_web", "type": "web", "priority": 0}]}, f)
    
    node_process = start_node()
    assert wait_for_task("shortlist_web"), "Web renderer did not start in time."
    
    try:
        response = requests.get("http://localhost:8003")
        assert response.status_code == 200
        assert "Shortlist" in response.text
    finally:
        node_process.kill()
        cleanup()
