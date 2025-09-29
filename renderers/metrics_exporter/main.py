import json
import os
import time
from datetime import datetime, timezone
import git
import psutil
from typing import Dict, List, Any, Optional
from flask import Flask, Response
from prometheus_client import Gauge, generate_latest
from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('metrics_exporter', log_level="INFO", log_file='/app/data/metrics.log')
logger = ComponentLogger('metrics_exporter')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='metrics_exporter')

# --- Configuration ---
DATA_DIR = '/app/data'
HEARTBEAT_TIMEOUT_SECONDS = 60  # Consider a task unhealthy if heartbeat is older than this

# --- Prometheus Metrics ---
# Swarm metrics
nodes_total = Gauge('shortlist_nodes_total', 'Total number of nodes in the roster')
nodes_alive = Gauge('shortlist_nodes_alive_total', 'Number of alive nodes in the swarm')
tasks_scheduled = Gauge('shortlist_tasks_scheduled_total', 'Total number of tasks in schedule.json')
tasks_assigned = Gauge('shortlist_tasks_assigned_total', 'Number of tasks currently assigned')

# Task metrics
task_assigned = Gauge(
    'shortlist_task_assigned_status',
    'Assignment status of a task (1=assigned, 0=unassigned)',
    ['task_id', 'task_type']
)

task_healthy = Gauge(
    'shortlist_task_healthy_status',
    'Health status of a task (1=healthy, 0=unhealthy)',
    ['task_id', 'task_type']
)

# Node metrics
node_cpu = Gauge('shortlist_node_cpu_load_percent', 'Current CPU load of a node', ['node_id'])
node_memory = Gauge('shortlist_node_memory_usage_percent', 'Current memory usage of a node', ['node_id'])
node_disk = Gauge('shortlist_node_disk_usage_percent', 'Current disk usage of a node', ['node_id'])
node_uptime = Gauge('shortlist_node_uptime_seconds', 'Node uptime in seconds', ['node_id'])

def sync_repo() -> None:
    """Sync the repository to get latest state."""
    try:
        repo = git.Repo(DATA_DIR)
        with log_operation(logger.logger, "git_sync"):
            repo.git.pull(rebase=True)
    except Exception as e:
        logger.logger.error("Failed to sync repository",
                          error=str(e),
                          error_type=type(e).__name__)

def read_json_file(filename: str) -> Optional[Dict[str, Any]]:
    """Read and parse a JSON file safely."""
    try:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.logger.error(f"Failed to read {filename}",
                          error=str(e),
                          error_type=type(e).__name__)
        return None

def is_node_alive(node: Dict[str, Any]) -> bool:
    """Check if a node is considered alive based on its heartbeat."""
    try:
        heartbeat = datetime.fromisoformat(node.get('heartbeat', ''))
        now = datetime.now(timezone.utc)
        return (now - heartbeat).total_seconds() < HEARTBEAT_TIMEOUT_SECONDS
    except:
        return False

def is_task_healthy(assignment: Dict[str, Any]) -> bool:
    """Check if a task is healthy based on its heartbeat."""
    try:
        heartbeat = datetime.fromisoformat(assignment.get('task_heartbeat', ''))
        now = datetime.now(timezone.utc)
        return (now - heartbeat).total_seconds() < HEARTBEAT_TIMEOUT_SECONDS
    except:
        return False

@log_execution_time(logger.logger)
def update_metrics() -> None:
    """Update all Prometheus metrics based on current state."""
    with log_operation(logger.logger, "update_metrics"):
        # Sync repository to get latest state
        sync_repo()
        
        # Read state files
        roster_data = read_json_file('roster.json') or {}
        schedule_data = read_json_file('schedule.json') or {}
        assignments_data = read_json_file('assignments.json') or {}
        
        # Update swarm metrics
        nodes = roster_data.get('nodes', [])
        nodes_total.set(len(nodes))
        nodes_alive.set(sum(1 for node in nodes if is_node_alive(node)))
        
        tasks = schedule_data.get('tasks', [])
        tasks_scheduled.set(len(tasks))
        tasks_assigned.set(len(assignments_data))
        
        # Reset task metrics (to clean up old tasks)
        task_assigned._metrics.clear()
        task_healthy._metrics.clear()
        
        # Update task metrics
        for task in tasks:
            task_id = task.get('id')
            task_type = task.get('type')
            if not task_id or not task_type:
                continue
                
            assignment = assignments_data.get(task_type, {})
            is_assigned = bool(assignment)
            task_assigned.labels(task_id=task_id, task_type=task_type).set(int(is_assigned))
            
            is_healthy = is_task_healthy(assignment) if is_assigned else 0
            task_healthy.labels(task_id=task_id, task_type=task_type).set(int(is_healthy))
        
        # Reset node metrics
        node_cpu._metrics.clear()
        node_memory._metrics.clear()
        node_disk._metrics.clear()
        node_uptime._metrics.clear()
        
        # Update node metrics
        for node in nodes:
            node_id = node.get('id')
            if not node_id:
                continue
                
            metrics = node.get('metrics', {})
            if metrics:
                node_cpu.labels(node_id=node_id).set(metrics.get('cpu_percent', 0))
                node_memory.labels(node_id=node_id).set(metrics.get('memory_percent', 0))
                node_disk.labels(node_id=node_id).set(metrics.get('disk_percent', 0))
                node_uptime.labels(node_id=node_id).set(metrics.get('uptime_seconds', 0))

# --- Web Server ---
app = Flask(__name__)

@app.route('/metrics')
def metrics() -> Response:
    """Prometheus metrics endpoint."""
    with log_operation(logger.logger, "serve_metrics"):
        update_metrics()
        return Response(generate_latest(), mimetype='text/plain')

@app.route('/')
def index() -> str:
    """Simple index page."""
    return '''
        <h1>Shortlist Metrics Exporter</h1>
        <p>Visit <a href="/metrics">/metrics</a> for Prometheus metrics.</p>
    '''

@app.route('/health')
def health() -> tuple[str, int]:
    """Health check endpoint."""
    return "ok", 200

def main() -> None:
    """Main entry point."""
    logger.log_startup()
    
    # Initial metrics update
    try:
        update_metrics()
    except Exception as e:
        logger.logger.error("Initial metrics update failed",
                          error=str(e),
                          error_type=type(e).__name__)
    
    # Start server
    logger.logger.info("Starting metrics exporter",
                      host='0.0.0.0',
                      port=8000)
    app.run(host='0.0.0.0', port=8000)
    logger.log_shutdown()

if __name__ == '__main__':
    main()