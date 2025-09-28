import os
import json
import logging
import requests
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
API_CONTAINER_NAME = os.getenv("API_CONTAINER_NAME", "shortlist_governance_api")
API_URL = f"http://{API_CONTAINER_NAME}:8000"
SHORTLIST_FILE = "/app/data/shortlist.json"
ROSTER_FILE = "/app/data/roster.json"
ASSIGNMENTS_FILE = "/app/data/assignments.json"

def read_json_file(filepath):
    """Read JSON file with error handling"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read {filepath}: {e}")
        return {}

def parse_items_from_text(text):
    """Parse shortlist items from textarea input"""
    try:
        # Try to parse as JSON first
        data = json.loads(text)
        if isinstance(data, dict) and "items" in data:
            return data["items"]
        elif isinstance(data, list):
            return data
        else:
            return [str(data)]
    except json.JSONDecodeError:
        # Fallback: treat as line-separated text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return lines

@app.route("/")
def index():
    """Serve the main HTML interface"""
    return render_template("index.html")

@app.route("/api/swarm-status")
def get_swarm_status():
    """Get comprehensive swarm status from local files"""
    try:
        roster = read_json_file(ROSTER_FILE)
        assignments = read_json_file(ASSIGNMENTS_FILE)
        shortlist = read_json_file(SHORTLIST_FILE)

        # Process roster data
        nodes = []
        current_time = datetime.utcnow().replace(tzinfo=timezone.utc)

        for node in roster.get("nodes", []):
            try:
                last_seen = datetime.fromisoformat(node["last_seen"].replace('Z', '+00:00'))
                time_diff = (current_time - last_seen).total_seconds()
                is_alive = time_diff < 300  # 5 minutes threshold

                nodes.append({
                    "id": node["id"][:8] + "...",
                    "full_id": node["id"],
                    "started_at": node.get("started_at", ""),
                    "last_seen": node["last_seen"],
                    "is_alive": is_alive,
                    "time_since_last_seen": f"{int(time_diff)}s ago"
                })
            except Exception as e:
                logger.warning(f"Error processing node {node.get('id', 'unknown')}: {e}")

        # Process assignments data
        tasks = []
        for task_id, assignment in assignments.get("assignments", {}).items():
            try:
                last_heartbeat = datetime.fromisoformat(assignment["task_heartbeat"].replace('Z', '+00:00'))
                time_diff = (current_time - last_heartbeat).total_seconds()
                is_healthy = time_diff < 120  # 2 minutes threshold

                tasks.append({
                    "task_id": task_id,
                    "node_id": assignment["node_id"][:8] + "...",
                    "full_node_id": assignment["node_id"],
                    "status": assignment.get("status", "unknown"),
                    "claimed_at": assignment.get("claimed_at", ""),
                    "task_heartbeat": assignment["task_heartbeat"],
                    "is_healthy": is_healthy,
                    "time_since_heartbeat": f"{int(time_diff)}s ago"
                })
            except Exception as e:
                logger.warning(f"Error processing task {task_id}: {e}")

        return jsonify({
            "nodes": nodes,
            "tasks": tasks,
            "shortlist": shortlist,
            "stats": {
                "total_nodes": len(nodes),
                "alive_nodes": sum(1 for n in nodes if n["is_alive"]),
                "total_tasks": len(tasks),
                "healthy_tasks": sum(1 for t in tasks if t["is_healthy"])
            },
            "timestamp": current_time.isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting swarm status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/shortlist-content")
def get_shortlist_content():
    """Get current shortlist content for editing"""
    try:
        shortlist = read_json_file(SHORTLIST_FILE)
        return jsonify({
            "content": json.dumps(shortlist, indent=2),
            "items": shortlist.get("items", [])
        })
    except Exception as e:
        logger.error(f"Error getting shortlist content: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/governance-status")
def get_governance_status():
    """Check if governance API is available"""
    try:
        # Read assignments to get the actual container name
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
        governance_assignment = assignments["assignments"].get("shortlist_governance_api")

        if not governance_assignment:
            return jsonify({
                "available": False,
                "error": "Governance API task not assigned to any node"
            })

        # Construct actual container name: task_id-node_id[:8]
        node_id = governance_assignment["node_id"]
        container_name = f"shortlist_governance_api-{node_id[:8]}"
        api_url = f"http://{container_name}:8000"

        response = requests.get(f"{api_url}/v1/status", timeout=5)
        if response.status_code == 200:
            return jsonify({
                "available": True,
                "status": response.json(),
                "container_name": container_name
            })
        else:
            return jsonify({
                "available": False,
                "error": f"API returned status {response.status_code}",
                "container_name": container_name
            })
    except requests.exceptions.RequestException as e:
        return jsonify({
            "available": False,
            "error": str(e)
        })

@app.route("/ui/propose", methods=["POST"])
def propose_change():
    """Proxy for contributor proposal endpoint"""
    try:
        data = request.json
        token = data.get("token")
        content_text = data.get("content", "")
        description = data.get("description", "Shortlist update via Admin UI")

        if not token:
            return jsonify({"error": "API token is required"}), 400

        # Parse content
        try:
            items = parse_items_from_text(content_text)
        except Exception as e:
            return jsonify({"error": f"Invalid content format: {str(e)}"}), 400

        # Get dynamic API URL
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
        governance_assignment = assignments["assignments"].get("shortlist_governance_api")

        if not governance_assignment:
            return jsonify({"error": "Governance API not available"}), 503

        node_id = governance_assignment["node_id"]
        container_name = f"shortlist_governance_api-{node_id[:8]}"
        api_url = f"http://{container_name}:8000"

        # Prepare request to governance API
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "items": items,
            "description": description
        }

        response = requests.post(
            f"{api_url}/v1/proposals/shortlist",
            json=payload,
            headers=headers,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        error_detail = "Connection error to governance API"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
            except:
                error_detail = e.response.text
        return jsonify({"error": error_detail}), 503
    except Exception as e:
        logger.error(f"Error in propose_change: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/ui/apply", methods=["POST"])
def apply_change():
    """Proxy for maintainer direct application endpoint"""
    try:
        data = request.json
        token = data.get("token")
        content_text = data.get("content", "")

        if not token:
            return jsonify({"error": "API token is required"}), 400

        # Parse content
        try:
            items = parse_items_from_text(content_text)
        except Exception as e:
            return jsonify({"error": f"Invalid content format: {str(e)}"}), 400

        # Get dynamic API URL
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
        governance_assignment = assignments["assignments"].get("shortlist_governance_api")

        if not governance_assignment:
            return jsonify({"error": "Governance API not available"}), 503

        node_id = governance_assignment["node_id"]
        container_name = f"shortlist_governance_api-{node_id[:8]}"
        api_url = f"http://{container_name}:8000"

        # Prepare request to governance API
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"items": items}

        response = requests.post(
            f"{api_url}/v1/admin/shortlist",
            json=payload,
            headers=headers,
            timeout=30
        )

        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        error_detail = "Connection error to governance API"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
            except:
                error_detail = e.response.text
        return jsonify({"error": error_detail}), 503
    except Exception as e:
        logger.error(f"Error in apply_change: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "service": "shortlist-admin-ui"
    })

if __name__ == "__main__":
    logger.info("Starting Shortlist Control Room...")
    logger.info(f"Governance API URL: {API_URL}")
    app.run(host="0.0.0.0", port=8000, debug=False)