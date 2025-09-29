import os
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('admin_ui_renderer', log_level="INFO", log_file='/app/data/admin_ui.log')
logger = ComponentLogger('admin_ui_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='admin_ui')

app = Flask(__name__)

# Configuration
API_CONTAINER_NAME = os.getenv("API_CONTAINER_NAME", "shortlist_governance_api")
API_URL = f"http://{API_CONTAINER_NAME}:8000"
SHORTLIST_FILE = "/app/data/shortlist.json"
ROSTER_FILE = "/app/data/roster.json"
ASSIGNMENTS_FILE = "/app/data/assignments.json"


def _resolve_governance_api_url() -> Optional[str]:
    """Resolve the current Governance API URL based on assignments.
    Returns the base URL like http://container-name:8000 or None if unavailable.
    """
    assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
    governance_assignment = assignments.get("assignments", {}).get("shortlist_governance_api")
    if not governance_assignment:
        return None
    node_id = governance_assignment.get("node_id")
    if not node_id:
        return None
    container_name = f"shortlist_governance_api-{node_id[:8]}"
    return f"http://{container_name}:8000"

@log_execution_time(logger.logger)
def read_json_file(filepath: str) -> Dict[str, Any]:
    """Read JSON file with error handling
    
    Args:
        filepath: Path to the JSON file to read
        
    Returns:
        Dict containing the file contents or empty dict on error
    """
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.logger.warning("Failed to read JSON file",
                            error=str(e),
                            error_type=type(e).__name__,
                            filepath=filepath)
        return {}

@log_execution_time(logger.logger)
def parse_items_from_text(text: str) -> List[str]:
    """Parse shortlist items from textarea input
    
    Args:
        text: Content to parse, either JSON or line-separated text
        
    Returns:
        List of parsed items
    """
    with log_operation(logger.logger, "parse_content", content_length=len(text)):
        try:
            # Try to parse as JSON first
            data = json.loads(text)
            if isinstance(data, dict) and "items" in data:
                items = data["items"]
                logger.logger.info("Parsed JSON object format", items_count=len(items))
                return items
            elif isinstance(data, list):
                logger.logger.info("Parsed JSON array format", items_count=len(data))
                return data
            else:
                logger.logger.info("Parsed single JSON value")
                return [str(data)]
        except json.JSONDecodeError:
            # Fallback: treat as line-separated text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            logger.logger.info("Parsed line-separated format", lines_count=len(lines))
            return lines

@app.route("/")
def index():
    """Serve the main HTML interface"""
    with log_operation(logger.logger, "serve_index",
                      path=request.path,
                      remote_addr=request.remote_addr):
        return render_template("index.html")

@app.route("/api/swarm-status")
def get_swarm_status():
    """Get comprehensive swarm status from local files"""
    with log_operation(logger.logger, "get_swarm_status",
                      path=request.path,
                      remote_addr=request.remote_addr):
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
                logger.logger.warning("Error processing node",
                                       node_id=node.get('id', 'unknown'),
                                       error=str(e))

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
                logger.logger.warning("Error processing task",
                                       task_id=task_id,
                                       error=str(e))

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
        logger.logger.error("Failed to get swarm status",
                          error=str(e),
                          error_type=type(e).__name__)
        return jsonify({"error": str(e)}), 500

@app.route("/api/shortlist-content")
def get_shortlist_content():
    """Get current shortlist content for editing"""
    with log_operation(logger.logger, "get_shortlist_content",
                      path=request.path,
                      remote_addr=request.remote_addr):
        try:
            shortlist = read_json_file(SHORTLIST_FILE)
        return jsonify({
            "content": json.dumps(shortlist, indent=2),
            "items": shortlist.get("items", [])
        })
    except Exception as e:
        logger.logger.error("Failed to get shortlist content",
                            error=str(e),
                            error_type=type(e).__name__)
        return jsonify({"error": str(e)}), 500

@app.route("/api/governance-status")
def get_governance_status():
    """Check if governance API is available"""
    with log_operation(logger.logger, "check_governance_status",
                      path=request.path,
                      remote_addr=request.remote_addr):
        try:
        # Read assignments to get the actual container name
        assignments = read_json_file(ASSIGNMENTS_FILE) or {"assignments": {}}
        governance_assignment = assignments["assignments"].get("shortlist_governance_api")

        if not governance_assignment:
            return jsonify({
                "available": False,
                "error": "task not assigned",
                "error_type": "no_assignment",
                "message": "No node has claimed the governance API task yet"
            })

        # Check if the task assignment is recent (heartbeat within last 2 minutes)
        from datetime import datetime, timezone, timedelta
        try:
            last_heartbeat = datetime.fromisoformat(governance_assignment.get("task_heartbeat", "1970-01-01T00:00:00+00:00"))
            if (datetime.now(timezone.utc) - last_heartbeat) > timedelta(minutes=2):
                return jsonify({
                    "available": False,
                    "error": "task assignment expired",
                    "error_type": "stale_assignment",
                    "message": f"Task assigned to node but heartbeat is stale (last: {governance_assignment.get('task_heartbeat', 'unknown')})"
                })
        except Exception:
            pass  # Continue with connection attempt

        # Construct actual container name: task_id-node_id[:8]
        node_id = governance_assignment["node_id"]
        container_name = f"shortlist_governance_api-{node_id[:8]}"
        api_url = f"http://{container_name}:8000"

        response = requests.get(f"{api_url}/v1/status", timeout=5)
        if response.status_code == 200:
            return jsonify({
                "available": True,
                "status": response.json(),
                "container_name": container_name,
                "node_id": node_id[:8]
            })
        else:
            return jsonify({
                "available": False,
                "error": f"API returned status {response.status_code}",
                "error_type": "http_error",
                "container_name": container_name
            })
    except requests.exceptions.ConnectionError as e:
        error_msg = str(e)
        if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
            return jsonify({
                "available": False,
                "error": "Service not running",
                "error_type": "container_not_running",
                "message": "The governance API container is not currently active"
            })
        else:
            return jsonify({
                "available": False,
                "error": "Connection failed",
                "error_type": "connection_error",
                "message": "Cannot connect to the governance API service"
            })
    except requests.exceptions.Timeout:
        return jsonify({
            "available": False,
            "error": "Service timeout",
            "error_type": "timeout",
            "message": "The governance API service is not responding"
        })
    except requests.exceptions.RequestException as e:
        return jsonify({
            "available": False,
            "error": str(e),
            "error_type": "request_error"
        })

@app.route("/ui/propose", methods=["POST"])
def propose_change():
    """Proxy for contributor proposal endpoint"""
    with log_operation(logger.logger, "propose_change",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
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
        logger.logger.error("Failed to propose change",
                            error=str(e),
                            error_type=type(e).__name__)
        return jsonify({"error": str(e)}), 500

@app.route("/ui/apply", methods=["POST"])
def apply_change():
    """Proxy for maintainer direct application endpoint"""
    with log_operation(logger.logger, "apply_change",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
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
        logger.logger.error("Failed to apply change",
                            error=str(e),
                            error_type=type(e).__name__)
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health_check():
    """Health check endpoint"""
    with log_operation(logger.logger, "health_check",
                      path=request.path,
                      remote_addr=request.remote_addr):
        return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "service": "shortlist-admin-ui"
    })


# --- New proxy endpoints for History & Revert ---
@app.route("/api/history", methods=["GET"])
def proxy_history():
    """Proxy to Governance API history endpoint.
    Expects ?token=MAINTAINER_API_TOKEN in query params.
    """
    with log_operation(logger.logger, "proxy_history",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
        try:
            token = request.args.get("token", "").strip()
            if not token:
                return jsonify({"error": "API token is required"}), 400

            api_url = _resolve_governance_api_url()
            if not api_url:
                return jsonify({"error": "Governance API not available"}), 503

            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(f"{api_url}/v1/admin/history", headers=headers, timeout=20)
            return Response(resp.content, status=resp.status_code, mimetype=resp.headers.get('Content-Type', 'application/json'))
        except requests.exceptions.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            logger.logger.error("History proxy failed", error=str(e), error_type=type(e).__name__)
            return jsonify({"error": str(e)}), 500


@app.route("/ui/revert", methods=["POST"])
def proxy_revert():
    """Proxy to Governance API revert endpoint.
    Body: { commit_hash, token }
    """
    with log_operation(logger.logger, "proxy_revert",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
        try:
            data = request.json or {}
            token = data.get("token", "").strip()
            commit_hash = data.get("commit_hash", "").strip()

            if not token:
                return jsonify({"error": "API token is required"}), 400
            if not commit_hash:
                return jsonify({"error": "commit_hash is required"}), 400

            api_url = _resolve_governance_api_url()
            if not api_url:
                return jsonify({"error": "Governance API not available"}), 503

            headers = {"Authorization": f"Bearer {token}"}
            payload = {"commit_hash": commit_hash}
            resp = requests.post(f"{api_url}/v1/admin/revert", json=payload, headers=headers, timeout=60)
            return Response(resp.content, status=resp.status_code, mimetype=resp.headers.get('Content-Type', 'application/json'))
        except requests.exceptions.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            logger.logger.error("Revert proxy failed", error=str(e), error_type=type(e).__name__)
            return jsonify({"error": str(e)}), 500


@app.route("/api/secrets", methods=["GET"]) 
def proxy_list_secrets():
    with log_operation(logger.logger, "proxy_list_secrets",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
        try:
            token = request.args.get("token", "").strip()
            if not token:
                return jsonify({"error": "API token is required"}), 400
            api_url = _resolve_governance_api_url()
            if not api_url:
                return jsonify({"error": "Governance API not available"}), 503
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.get(f"{api_url}/v1/admin/secrets", headers=headers, timeout=20)
            return Response(r.content, status=r.status_code, mimetype=r.headers.get('Content-Type', 'application/json'))
        except requests.exceptions.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            logger.logger.error("Secrets list proxy failed", error=str(e), error_type=type(e).__name__)
            return jsonify({"error": str(e)}), 500


@app.route("/ui/secrets", methods=["POST", "DELETE"]) 
def proxy_mutate_secrets():
    with log_operation(logger.logger, "proxy_mutate_secrets",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
        try:
            data = request.json or {}
            token = data.get("token", "").strip()
            if not token:
                return jsonify({"error": "API token is required"}), 400
            api_url = _resolve_governance_api_url()
            if not api_url:
                return jsonify({"error": "Governance API not available"}), 503
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            if request.method == 'POST':
                payload = {"key": data.get("key", ""), "value": data.get("value", "")}
                r = requests.post(f"{api_url}/v1/admin/secrets", json=payload, headers=headers, timeout=20)
            else:
                payload = {"key": data.get("key", "")}
                r = requests.delete(f"{api_url}/v1/admin/secrets", json=payload, headers=headers, timeout=20)
            return Response(r.content, status=r.status_code, mimetype=r.headers.get('Content-Type', 'application/json'))
        except requests.exceptions.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            logger.logger.error("Secrets mutate proxy failed", error=str(e), error_type=type(e).__name__)
            return jsonify({"error": str(e)}), 500


@app.route("/ui/preview", methods=["POST"]) 
def proxy_preview():
    """Proxy preview generation to Governance API with streaming response."""
    with log_operation(logger.logger, "proxy_preview",
                      path=request.path,
                      method=request.method,
                      remote_addr=request.remote_addr):
        try:
            data = request.json or {}
            token = data.get("token", "").strip()
            renderer_type = data.get("renderer_type", "")
            content = data.get("content")

            if not token:
                return jsonify({"error": "API token is required"}), 400
            if renderer_type not in ("audio", "video"):
                return jsonify({"error": "renderer_type must be 'audio' or 'video'"}), 400
            if not isinstance(content, dict):
                return jsonify({"error": "content must be a JSON object"}), 400

            api_url = _resolve_governance_api_url()
            if not api_url:
                return jsonify({"error": "Governance API not available"}), 503

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            # Stream the response from the API to the client
            with requests.post(f"{api_url}/v1/admin/preview", json={
                "renderer_type": renderer_type,
                "content": content
            }, headers=headers, stream=True, timeout=600) as r:
                def generate():
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                # Pass through status and content-type
                return Response(stream_with_context(generate()), status=r.status_code, headers={
                    'Content-Type': r.headers.get('Content-Type', 'application/octet-stream'),
                    'Content-Disposition': r.headers.get('Content-Disposition', '')
                })
        except requests.exceptions.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            logger.logger.error("Preview proxy failed", error=str(e), error_type=type(e).__name__)
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.log_startup(
        service="Shortlist Control Room",
        api_url=API_URL,
        host="0.0.0.0",
        port=8000
    )
    app.run(host="0.0.0.0", port=8000, debug=False)
    logger.log_shutdown()
