# 🔭 Observability & Monitoring

Shortlist includes a built-in metrics exporter that exposes system state and health metrics in Prometheus format. This allows integration with standard monitoring tools like Prometheus and Grafana to visualize and alert on swarm health, task status, and node performance.

## Metrics Endpoint

The Shortlist metrics exporter exposes metrics at:
```
http://localhost:9091/metrics
```

## Available Metrics

### Swarm State
| Metric Name | Type | Description |
|------------|------|-------------|
| `shortlist_nodes_total` | Gauge | Total number of nodes in the roster |
| `shortlist_nodes_alive_total` | Gauge | Number of nodes considered "alive" |
| `shortlist_tasks_scheduled_total` | Gauge | Number of tasks in schedule.json |
| `shortlist_tasks_assigned_total` | Gauge | Number of tasks currently assigned |

### Task State
| Metric Name | Type | Labels | Description |
|------------|------|--------|-------------|
| `shortlist_task_assigned_status` | Gauge | `task_id`, `task_type` | Assignment status (1=assigned, 0=unassigned) |
| `shortlist_task_healthy_status` | Gauge | `task_id`, `task_type` | Health status (1=healthy, 0=unhealthy) |

### Node Metrics
| Metric Name | Type | Labels | Description |
|------------|------|--------|-------------|
| `shortlist_node_cpu_load_percent` | Gauge | `node_id` | CPU load percentage per node |
| `shortlist_node_memory_usage_percent` | Gauge | `node_id` | Memory usage percentage per node |
| `shortlist_node_disk_usage_percent` | Gauge | `node_id` | Disk usage percentage per node |
| `shortlist_node_uptime_seconds` | Gauge | `node_id` | Node uptime in seconds |

## Example Metrics Output

```
# HELP shortlist_nodes_alive_total Number of alive nodes in the swarm
# TYPE shortlist_nodes_alive_total gauge
shortlist_nodes_alive_total 3

# HELP shortlist_task_healthy_status Health status of a task (1=healthy, 0=unhealthy)
# TYPE shortlist_task_healthy_status gauge
shortlist_task_healthy_status{task_id="shortlist_governance_api",task_type="api"} 1
shortlist_task_healthy_status{task_id="shortlist_admin_ui",task_type="admin_ui"} 1
shortlist_task_healthy_status{task_id="icecast_audio_stream",task_type="audio"} 0

# HELP shortlist_node_cpu_load_percent Current CPU load of a node
# TYPE shortlist_node_cpu_load_percent gauge
shortlist_node_cpu_load_percent{node_id="node-uuid-123"} 15.7
shortlist_node_cpu_load_percent{node_id="node-uuid-456"} 22.1
```

## Integration with Prometheus

1. Add the following scrape configuration to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'shortlist_swarm'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['localhost:9091']
    scrape_interval: 15s
```

2. Restart Prometheus to apply the configuration
3. The metrics will appear in Prometheus with the prefix `shortlist_`

## Grafana Dashboards

You can create Grafana dashboards to visualize Shortlist metrics. Here are some suggested panels:

### Swarm Health
- Graph of active nodes over time (`shortlist_nodes_alive_total`)
- Task assignment rate (`shortlist_tasks_assigned_total` / `shortlist_tasks_scheduled_total`)
- Task health status heatmap using `shortlist_task_healthy_status`

### Node Performance
- CPU usage per node (`shortlist_node_cpu_load_percent`)
- Memory usage per node (`shortlist_node_memory_usage_percent`)
- Disk usage alerts when approaching capacity

### Task Status
- Task health status table with labels
- Task assignment timeline
- Health check failure alerts

## Example Grafana Dashboard JSON

Here's a starter Grafana dashboard that includes the essential panels:

```json
{
  "title": "Shortlist Swarm Overview",
  "panels": [
    {
      "title": "Active Nodes",
      "type": "gauge",
      "datasource": "Prometheus",
      "targets": [
        {
          "expr": "shortlist_nodes_alive_total",
          "instant": true
        }
      ],
      "options": {
        "minValue": 0,
        "maxValue": 10,
        "thresholds": [
          { "value": 0, "color": "red" },
          { "value": 1, "color": "yellow" },
          { "value": 2, "color": "green" }
        ]
      }
    },
    {
      "title": "Task Health Matrix",
      "type": "heatmap",
      "datasource": "Prometheus",
      "targets": [
        {
          "expr": "shortlist_task_healthy_status",
          "format": "time_series",
          "legendFormat": "{{task_type}}"
        }
      ]
    },
    {
      "title": "Node CPU Usage",
      "type": "graph",
      "datasource": "Prometheus",
      "targets": [
        {
          "expr": "shortlist_node_cpu_load_percent",
          "legendFormat": "{{node_id}}"
        }
      ],
      "yaxes": [
        {
          "format": "percent",
          "min": 0,
          "max": 100
        }
      ]
    }
  ]
}
```

## Alert Rules

Here are some recommended Prometheus alert rules for Shortlist monitoring:

```yaml
groups:
- name: shortlist_alerts
  rules:
  - alert: NodesDown
    expr: shortlist_nodes_alive_total < 2
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Not enough nodes available"
      description: "Only {{ $value }} nodes are alive"

  - alert: TaskUnhealthy
    expr: shortlist_task_healthy_status == 0
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Task is unhealthy"
      description: "Task {{ $labels.task_id }} ({{ $labels.task_type }}) is reporting as unhealthy"

  - alert: HighNodeCPU
    expr: shortlist_node_cpu_load_percent > 85
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage"
      description: "Node {{ $labels.node_id }} CPU usage is {{ $value }}%"
```

## Monitoring Best Practices

1. **Health Checks**
   - Set up alerts for when task health drops to 0
   - Monitor the number of alive nodes
   - Watch for trends in CPU and memory usage

2. **Data Retention**
   - Configure Prometheus with appropriate retention periods
   - Use recording rules for frequently accessed queries
   - Consider using remote storage for long-term metrics

3. **Dashboard Organization**
   - Create separate dashboards for different audiences:
     - Overview dashboard for general status
     - Detailed dashboard for debugging
     - SLA/uptime dashboard for reliability tracking

4. **Alert Configuration**
   - Set appropriate thresholds based on your SLOs
   - Use "for" duration to prevent alert flapping
   - Configure proper alerting channels and escalation