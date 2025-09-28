import subprocess
import time
import requests

from test_utils import (
    NODE_PY, SCHEDULE_FILE, ASSIGNMENTS_FILE, ROSTER_FILE,
    PORT_DASHBOARD, PORT_AUDIO, PORT_API, PORT_WEB,
    create_task, write_json_file
)

# --- Helper Functions ---
def cleanup():
    subprocess.run(["pkill", "-f", str(NODE_PY)], check=False)
    container_ids = subprocess.check_output(["docker", "ps", "-aq"]).decode("utf-8").split()
    if container_ids:
        subprocess.run(["docker", "stop"] + container_ids, check=False)
        subprocess.run(["docker", "rm"] + container_ids, check=False)
    # Initialize empty state files
    write_json_file(ASSIGNMENTS_FILE, {})
    write_json_file(ROSTER_FILE, {})

def start_node():
    return subprocess.Popen(["python3", str(NODE_PY)])

def wait_for_task(task_id: str, timeout: int = 60) -> bool:
    """Wait for a task to be in streaming state."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            assignments = read_json_file(ASSIGNMENTS_FILE)
            if task_id in assignments.get("assignments", {}) and \
               assignments["assignments"][task_id]["status"] == "streaming":
                return True
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(1)
    return False

# --- Tests ---

def test_dashboard_renderer():
    cleanup()
    write_json_file(SCHEDULE_FILE, {
        "tasks": [create_task("swarm_status_dashboard", "dashboard", priority=0)]
    })
    
    node_process = start_node()
    assert wait_for_task("swarm_status_dashboard"), "Dashboard renderer did not start in time."
    
    try:
        response = requests.get(f"http://localhost:{PORT_DASHBOARD}")
        assert response.status_code == 200
        assert "Swarm Dashboard" in response.text
    finally:
        node_process.kill()
        cleanup()

def test_audio_renderer():
    cleanup()
    write_json_file(SCHEDULE_FILE, {
        "tasks": [create_task("self_hosted_audio_stream", "audio", priority=0)]
    })
    
    node_process = start_node()
    assert wait_for_task("self_hosted_audio_stream"), "Audio renderer did not start in time."
    
    try:
        response = requests.get(f"http://localhost:{PORT_AUDIO}")
        assert response.status_code == 200
    finally:
        node_process.kill()
        cleanup()

def test_text_renderer():
    cleanup()
    write_json_file(SCHEDULE_FILE, {
        "tasks": [create_task("telegram_text_posts", "text", priority=0)]
    })
    
    node_process = start_node()
    assert wait_for_task("telegram_text_posts"), "Text renderer did not start in time."
    
    # The text renderer does not expose a port, so we just check if it starts.
    # A more advanced test could check the output of the container.
    node_process.kill()
    cleanup()

def test_api_renderer():
    cleanup()
    write_json_file(SCHEDULE_FILE, {
        "tasks": [create_task("shortlist_api", "api", priority=0)]
    })
    
    node_process = start_node()
    assert wait_for_task("shortlist_api"), "API renderer did not start in time."
    
    try:
        response = requests.get(f"http://localhost:{PORT_API}/api/shortlist")
        assert response.status_code == 200
        assert "items" in response.json()
    finally:
        node_process.kill()
        cleanup()

def test_web_renderer():
    cleanup()
    write_json_file(SCHEDULE_FILE, {
        "tasks": [create_task("shortlist_web", "web", priority=0)]
    })
    
    node_process = start_node()
    assert wait_for_task("shortlist_web"), "Web renderer did not start in time."
    
    try:
        response = requests.get(f"http://localhost:{PORT_WEB}")
        assert response.status_code == 200
        assert "Shortlist" in response.text
    finally:
        node_process.kill()
        cleanup()
