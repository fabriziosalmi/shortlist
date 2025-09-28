from flask import Flask, jsonify, Response, request
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('dashboard_renderer', log_level="INFO", log_file='/app/data/dashboard.log')
logger = ComponentLogger('dashboard_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='dashboard')

app = Flask(__name__)

STATE_FILES = {
    'roster': '/app/data/roster.json',
    'schedule': '/app/data/schedule.json',
    'assignments': '/app/data/assignments.json'
}

@log_execution_time(logger.logger)
def read_json_file(filepath: str) -> Dict[str, Any]:
    """Read a JSON file with error handling.
    
    Args:
        filepath: Path to the JSON file
        
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

@app.route('/')
def index():
    """Serve the main dashboard interface."""
    with log_operation(logger.logger, "serve_index",
                      path=request.path,
                      remote_addr=request.remote_addr):
        html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Shortlist - Swarm Dashboard</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 2em; }
            .container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 2em; }
            .card { background: #1e1e1e; border-radius: 8px; padding: 1.5em; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
            h1, h2 { color: #bb86fc; border-bottom: 2px solid #373737; padding-bottom: 0.5em; }
            h1 { text-align: center; grid-column: 1 / -1; }
            ul { list-style: none; padding: 0; }
            li { background: #2c2c2c; margin-bottom: 0.8em; padding: 1em; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
            .node-id, .task-id { font-family: monospace; font-size: 0.9em; color: #90caf9; }
            .status { font-weight: bold; }
            .status-streaming { color: #81c784; }
            .status-claiming { color: #ffb74d; }
            .timestamp { font-size: 0.8em; color: #9e9e9e; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Swarm Dashboard</h1>
            <div class="card" id="nodes-card"><h2>Active Nodes</h2><ul></ul></div>
            <div class="card" id="assignments-card"><h2>Assigned Tasks</h2><ul></ul></div>
        </div>
        <script>
            async function fetchData() {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                const nodesList = document.querySelector('#nodes-card ul');
                nodesList.innerHTML = '';
                data.roster.nodes.forEach(node => {
                    const li = document.createElement('li');
                    const lastSeen = new Date(node.last_seen).toLocaleString();
                    li.innerHTML = `<div><span class="node-id">${node.id.substring(0,13)}...</span></div><div class="timestamp">Last seen: ${lastSeen}</div>`;
                    nodesList.appendChild(li);
                });

                const assignmentsList = document.querySelector('#assignments-card ul');
                assignmentsList.innerHTML = '';
                for (const [taskId, assignment] of Object.entries(data.assignments.assignments)) {
                    const li = document.createElement('li');
                    const heartbeat = new Date(assignment.task_heartbeat).toLocaleTimeString();
                    li.innerHTML = `<div><span class="task-id">${taskId}</span><br><span class="node-id">→ ${assignment.node_id.substring(0,8)}...</span></div><div><span class="status status-${assignment.status}">${assignment.status}</span><br><span class="timestamp">Heartbeat: ${heartbeat}</span></div>`;
                    assignmentsList.appendChild(li);
                }
            }
            fetchData();
            setInterval(fetchData, 5000); // Aggiorna ogni 5 secondi
        </script>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

@app.route('/api/status')
def api_status():
    """Provide API endpoint for dashboard status data."""
    with log_operation(logger.logger, "get_status",
                      path=request.path,
                      remote_addr=request.remote_addr):
        status_data = {}
        for name, filepath in STATE_FILES.items():
            status_data[name] = read_json_file(filepath)
            
        logger.logger.info("Status data collected",
                          roster_nodes=len(status_data.get('roster', {}).get('nodes', [])),
                          assignments=len(status_data.get('assignments', {}).get('assignments', {})))
        return jsonify(status_data)

if __name__ == '__main__':
    logger.log_startup(
        service="Shortlist Dashboard",
        host="0.0.0.0",
        port=8000
    )
    app.run(host='0.0.0.0', port=8000)
    logger.log_shutdown()
