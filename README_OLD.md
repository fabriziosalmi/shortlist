# Shortlist: A Decentralized Broadcasting Swarm

**Shortlist** is a decentralized, resilient, and transparent system that allows a community to collectively broadcast a shared message—a "shortlist" of important topics—across multiple platforms simultaneously.

It operates as a **leaderless swarm** of independent nodes that coordinate their actions using a Git repository as their single source of truth and coordination backend. No central server, no single point of failure.

---

## Core Concepts

This project is an experiment in decentralized collaboration. The key principles are:

- **Decentralization:** There is no central orchestrator. Any machine that can run the `node.py` script can join the swarm and contribute to the broadcasting effort.
- **Resilience:** The swarm is self-healing at multiple levels:
  - **Node Failure Recovery:** If a node responsible for a broadcast task dies, another node will automatically detect the failure and take over the task.
  - **Service Health Monitoring:** Nodes actively monitor their renderers through health check endpoints, ensuring services remain truly responsive and not just running.
- **Transparency:** The entire state of the swarm—who is active, what tasks are being performed, and by whom—is publicly visible and auditable through the Git history of this repository.
- **Git as a Backend:** Instead of complex coordination services like Zookeeper or etcd, the swarm uses Git itself as a distributed lock and state machine, making the system surprisingly simple and robust.

## How It Works

### Time-Based Item Scheduling

Shortlist supports time-based scheduling for individual items. Each item in your shortlist can have an optional `schedule` field that specifies when the item should be active. When no schedule is specified, items are always active.

#### Scheduling Example

```json
{
  "items": [
    {
      "id": "daily_greeting_morning",
      "content": "Good morning and welcome to our daily update!",
      "schedule": "0 8 * * 1-5"  // At 8:00 AM, Monday through Friday
    },
    {
      "id": "lunch_announcement",
      "content": "It's lunch time! Don't forget to take a break.",
      "schedule": "0 12 * * *"  // At 12:00 PM, every day
    },
    {
      "id": "weekend_message",
      "content": "Welcome to the weekend edition!",
      "schedule": "0 10 * * 6,0"  // At 10:00 AM, Saturday and Sunday
    },
    {
      "id": "always_active",
      "content": "This message appears in every rendering."
      // No schedule means always active
    }
  ]
}
```

#### Schedule Format

Schedules use the standard cron format with five fields:
```
minute  hour  day-of-month  month  day-of-week
```

Examples:
- `0 8 * * 1-5`: Every weekday at 8:00 AM
- `*/15 * * * *`: Every 15 minutes
- `0 9-17/2 * * *`: Every 2 hours from 9 AM to 5 PM

For help with cron expressions, visit [crontab.guru](https://crontab.guru).

Each renderer is "time-aware" and will only include items whose schedules match the current time. This allows you to create dynamic content that changes throughout the day, week, or month without manual intervention.

For detailed information about scheduling, see [SCHEDULING.md](SCHEDULING.md).

## How It Works

The system is composed of several key components:

#### 1. State Files

The entire state of the swarm is defined by a few JSON files in this repository:

- `shortlist.json`: The content to be broadcast. This is the only file you should manually edit.
- `roster.json`: A list of all active nodes in the swarm. Each node maintains its own entry with a periodic "heartbeat".
- `schedule.json`: Defines the broadcasting "tasks" that the swarm needs to perform with priority-based ordering (governance API, control room, dashboard, content renderers).
- `assignments.json`: A real-time map of which node is currently performing which task. This is the swarm's coordination "whiteboard".

#### 2. The Node (`node.py`)

This is the heart of the system. Each running instance of `node.py` is an independent member of the swarm. Each node operates as a state machine:

- **`IDLE`**: The node is alive and looking for work. It scans the `schedule.json` and `assignments.json` to find free or "orphan" tasks (tasks whose controlling node has gone silent).
- **`ATTEMPT_CLAIM`**: When a free task is found, the node waits a random "jitter" period to avoid conflicts with other nodes. It then attempts to "claim" the task by writing its ID to `assignments.json` and pushing the change. It uses Git's atomic nature to ensure only one node can claim a task at a time.
- **`ACTIVE`**: Once a task is claimed, the node enters the `ACTIVE` state. It launches the appropriate **Renderer** and continuously sends a "task heartbeat" to `assignments.json` to signal that it is still alive and in control of the task.

If a node crashes, its heartbeats stop, and the task it was performing becomes "orphan", ready to be claimed by another `IDLE` node.

#### 3. The Renderers

Renderers are the "muscles" of the swarm. They are containerized applications (managed by Docker) that perform the actual broadcasting.

- Each renderer is specialized for a task type and runs on a dedicated port
- The `node.py` script orchestrates these renderers, starting and stopping their containers as needed
- This design keeps dependencies isolated and allows for new broadcast platforms to be added easily

---

## 🧠 Adaptive Swarm: The Autonomous Core

The Shortlist swarm is now equipped with autonomous capabilities, allowing it to adapt and self-heal based on real-time metrics and predefined rules. This is achieved through the integration of two new systemic renderers: the Governor and the Healer.

### ⚡ Efficient State Management

Shortlist optimizes Git operations through intelligent batching:

#### Batched Operations
- System components (healer, governor) accumulate changes and commit them together
- Multiple state updates are combined into single Git operations
- Intelligent commit messages describe all included changes

Example batch operation:
```python
with batch_manager as batch:
    # All these changes will be committed together
    batch.stage_json_update(
        "assignments.json",
        assignments_data,
        "Release orphaned tasks"
    )
    batch.stage_json_update(
        "roster.json",
        roster_data,
        "Remove dead nodes"
    )
# Changes are automatically committed on exit
```

Benefits:
- Reduced Git write traffic
- Cleaner commit history
- Atomic multi-file updates
- Better context in commit messages

### 👀 Node Self-Awareness & Health Monitoring

#### System Metrics
Every node monitors its own performance (CPU, memory) and reports it in real-time, transforming the swarm into a sensory system. This data is crucial for the Governor to make informed decisions.

#### Active Health Checks
Nodes perform continuous health monitoring of their renderer services:
- Every 20 seconds, nodes ping their renderer's `/health` endpoint
- If a service fails to respond properly 3 times in a row, it's considered unhealthy
- Unhealthy services are automatically stopped and their tasks released
- This prevents "zombie services" that appear running but are actually unresponsive

This active monitoring ensures the swarm maintains true service availability, not just process status.

### The Governor (`governor`)
A strategic 'brain' with **Priority -2** that dynamically adapts the swarm's tasks (by modifying `schedule.json`) based on rules defined in `triggers.json`. This allows the swarm to react to temporal events or changes in overall health status.

#### Quorum System for Safe Decision Making
To prevent the governor from making critical decisions when the swarm is in a degraded state, triggers can specify quorum requirements. A quorum defines the minimum number of healthy nodes (either absolute or as a percentage) that must be active for a trigger to be evaluated. This safeguard ensures that major changes only occur when the swarm has sufficient consensus.

Example trigger with quorum requirements:
```json
{
  "id": "emergency_scale_down",
  "description": "Reduce resource usage under high load",
  "quorum": {
    "min_nodes_alive": 3,      // At least 3 nodes must be alive
    "min_percent_alive": 60    // At least 60% of all nodes must be alive
  },
  "condition": {
    "type": "swarm_metric_agg",
    "metric": "cpu_load",
    "aggregate": "average",
    "operator": ">",
    "threshold": 90
  },
  "action": {
    "type": "remove_task",
    "task_id": "video_stream"
  }
}
```

Quorum rules are optional. If not specified, a trigger will be evaluated regardless of swarm health. This is useful for non-critical operations like time-based task scheduling.

### The Healer (`healer`)
An 'immune system' with **Priority -1** that continuously scans the swarm's state and automatically corrects inconsistencies, such as task assignments left by 'dead' nodes (zombie assignments), ensuring long-term coherence.

---

**Currently Available Renderers (by priority):**

- **🧠 Governor** (`governor`) - **Priority -2**: Strategic 'brain' that adapts swarm tasks based on `triggers.json`
- **🩹 Healer** (`healer`) - **Priority -1**: 'Immune system' that corrects state inconsistencies like zombie assignments
- **🛡️ Governance API** (`api`) - Port 8004 - **Priority 0**: Secure API for shortlist management with tiered access control
- **🎛️ Control Room** (`admin_ui`) - Port 8005 - **Priority 1**: **PRIMARY INTERFACE** - Complete monitoring, governance, and editing
- **📊 Dashboard** (`dashboard`) - Port 8000 - **Priority 2**: Basic swarm status monitoring
- **📱 Telegram Text** (`text`) - **Priority 3**: Social media posting via Telegram bot
- **🎵 Audio Stream** (`audio`) - Port 8001 - **Priority 4**: Text-to-Speech audio with web player
- **🎬 Video Stream** (`video`) - Port 8002 - **Priority 5**: MP4 video with synchronized TTS audio
- **🌐 Web Interface** (`web`) - Port 8003 - **Priority 6**: Simple HTML content display

---

## Current Features

The Shortlist system currently includes the following working renderers:

### 📊 Dashboard Renderer
- **Real-time monitoring** of all swarm nodes and their status
- **Task assignment visualization** showing which node is handling what
- **System health overview** with heartbeat monitoring
- **Web-based interface** accessible at http://localhost:8000

### 🎵 Audio Renderer
- **Text-to-Speech generation** using Google TTS
- **Automatic audio looping** with pauses between items
- **Web audio player** with HTML5 controls
- **MP3 streaming** accessible at http://localhost:8001

### 🎬 Video Renderer

### 🚀 Live Streamer Renderer
- Continuous 24/7 live streaming to RTMP platforms (YouTube, Twitch, etc.)
- Dynamically updates content when shortlist.json changes
- Robust FFmpeg management with automatic restart on failure
- Secure stream key handling using the Control Room secrets system

Basic task configuration example (in schedule.json):
```json
{
  "id": "youtube_live_stream_247",
  "type": "live_streamer",
  "priority": 5,
  "config": {
    "platform": "youtube",
    "rtmp_url": "rtmp://a.rtmp.youtube.com/live2",
    "stream_key_secret_name": "YOUTUBE_STREAM_KEY",
    "video": { "resolution": "1280x720", "framerate": 24, "bitrate": "2500k" },
    "audio": { "bitrate": "128k" }
  }
}
```

How it works:
- The renderer generates a rolling playlist from shortlist items
- FFmpeg reads the playlist and streams continuously via RTMP
- When shortlist.json is updated, the playlist is atomically replaced,
  so the stream content changes without interruption
- **MP4 video generation** with visual text display
- **Synchronized TTS audio** embedded in video
- **Clean visual design** with centered text on black background
- **Dynamic duration** based on content length
- **HTML5 video player** accessible at http://localhost:8002

### 🌐 Web Renderer
- **Simple HTML interface** displaying shortlist items
- **Lightweight and fast** for basic content viewing
- **Mobile-friendly** responsive design
- **Direct content access** at http://localhost:8003

### Dynamic Content with Jinja2 Templating
- **Global Data Context**: Define reusable data in a dedicated `data` section
- **Template Processing**: Use Jinja2 syntax in any text field
- **Advanced Features**: Loops, conditionals, filters, and more
- **Safe Execution**: Sandboxed environment for secure template processing

Example shortlist.json with templates:
```json
{
  "data": {
    "company": {
      "name": "TechCorp",
      "current_milestone": "Series B"
    },
    "report": {
      "period": "Q4 2025",
      "team": {
        "lead": "Dr. Eva Rostova",
        "size": 42,
        "locations": ["San Francisco", "London", "Tokyo"]
      }
    }
  },
  "items": [
    {
      "id": "company_update",
      "type": "text",
      "content": "{{ company.name }} ({{ company.current_milestone }}) - {{ report.period }} Update"
    },
    {
      "id": "team_status",
      "type": "text",
      "content": "Our {{ report.team.size }}-person team, led by {{ report.team.lead }}, operates from {% for loc in report.team.locations %}{{ loc }}{% if not loop.last %}, {% endif %}{% endfor %}."
    }
  ]
}
```

When rendered, the above templates would produce:
```text
TechCorp (Series B) - Q4 2025 Update
Our 42-person team, led by Dr. Eva Rostova, operates from San Francisco, London, Tokyo.
```

### 🛡️ API Renderer (Governance)
- **Two-tier access control** with Maintainer and Contributor levels
- **Automated Pull Request workflow** for secure content updates
- **GitHub integration** with branch protection and approval flows
- **RESTful API** with FastAPI and automatic documentation
- **Audit trail** through GitHub's built-in version control

### 🎛️ Control Room (Admin UI) - **PRIMARY INTERFACE**
- **🌐 Real-time swarm monitoring** with live node and task status updates
- **🛡️ Governance API integration** with intelligent error handling and user-friendly status display
- **📝 Advanced shortlist editor** supporting both JSON and line-separated text formats
- **🔄 Auto-refresh functionality** with configurable intervals for live updates
- **⌨️ Keyboard shortcuts** (Ctrl+R refresh, Ctrl+S save) and rich notifications
- **📊 Smart error categorization** with helpful guidance for troubleshooting
- **🎨 Professional UI/UX** with structured error states and actionable help text
- **🔒 Secure proxy architecture** protecting governance API credentials from browser exposure
- **📱 Responsive design** optimized for both desktop and mobile interfaces
- **⚡ Performance optimized** with intelligent caching and minimal resource usage

### 📱 Text Renderer
- **Telegram bot integration** for social media posting
- **Automatic content broadcasting** to configured channels
- **External API integration** with proper authentication

---

## Quick Start

Want to see it in action immediately? Here's the fastest way:

```bash
git clone <your_repository_url>
cd shortlist
python3 node.py
```

### 🎛️ **PRIMARY INTERFACE - Control Room**
**Start here:** http://localhost:8005

The **Control Room** is your main dashboard providing:
- 🌐 **Live swarm monitoring** with real-time node and task status
- 🛡️ **Governance API status** with intelligent error handling
- 📝 **Shortlist editor** with both JSON and text format support
- 🔄 **Auto-refresh** every 5 seconds for live updates
- ⌨️ **Keyboard shortcuts** (Ctrl+R, Ctrl+S) for power users

### 📊 **Additional Interfaces**
- **Dashboard**: http://localhost:8000 - Basic swarm status monitoring
- **Audio Stream**: http://localhost:8001 - Text-to-Speech audio with web player
- **Video Stream**: http://localhost:8002 - MP4 video with synchronized audio
- **Web Interface**: http://localhost:8003 - Simple HTML content display
- **API Documentation**: http://localhost:8004/docs - Governance API (requires environment setup)

The system will automatically start generating content from `shortlist.json` and you can monitor the entire swarm coordination in real-time through the Control Room!

## 🎛️ Control Room - Primary Interface

The **Control Room** (port 8005) is your main dashboard for monitoring and managing the entire Shortlist system. It provides a **professional, user-friendly interface** with advanced error handling and real-time updates.

### **📋 Three Main Sections:**
1. **🌐 Swarm Status** - Real-time monitoring of all nodes and task assignments with health indicators
2. **🛡️ Governance API** - Integration status with intelligent error categorization and helpful guidance
3. **📝 Shortlist Editor** - Live editing interface supporting both JSON and line-separated formats

### **✨ Advanced Features:**
- **🔄 Smart auto-refresh** with configurable intervals (5-60 seconds)
- **⌨️ Keyboard shortcuts** (Ctrl+R refresh, Ctrl+S save, Escape cancel)
- **🔒 Secure proxy architecture** protecting governance API credentials from browser exposure
- **📊 Real-time statistics** showing alive nodes, healthy tasks, and system performance
- **🎨 Professional error handling** with structured, user-friendly error states
- **💡 Contextual help** with actionable guidance for resolving issues
- **📱 Responsive design** optimized for desktop and mobile devices
- **⚡ Performance optimization** with intelligent caching and minimal resource usage

### **🛡️ Enhanced Governance API Integration:**
The Control Room now provides **intelligent error categorization** for governance API issues:

- **🚫 Task not assigned** - Clear guidance when no node has claimed the task
- **⏰ Stale assignment** - Detection of inactive nodes with expired heartbeats
- **🔌 Service not running** - User-friendly explanation when containers aren't active
- **🌐 Connection issues** - Helpful troubleshooting for network problems
- **⏱️ Service timeouts** - Clear indication of unresponsive services
- **💡 Setup guidance** - Step-by-step instructions for enabling governance features

### **📊 Task Priority System:**
The swarm coordinates tasks based on priority (0 = highest):
0. **🛡️ Governance API** - Secure content management infrastructure
1. **🎛️ Control Room** - Primary monitoring and management interface
2. **📊 Dashboard** - Basic status monitoring
3. **📱 Telegram Text** - Social media broadcasting
4. **🎵 Audio Stream** - TTS content generation
5. **🎬 Video Stream** - Video content with synchronized audio
6. **🌐 Web Interface** - Simple HTML content display

---

## Node Roles and Specialization

Shortlist nodes can now specialize in specific types of tasks through roles. This allows for better resource utilization and more efficient task distribution.

### Available Roles

- **system**: Core system tasks (governor, healer, API)
- **media**: Audio and video rendering
- **web**: Web interfaces and dashboards
- **broadcaster**: Social media integration

### Running a Specialized Node

By default, nodes accept all roles for backward compatibility. To specialize a node:

```bash
# Run a system node (governor, healer, API)
python node.py --roles system

# Run a media processing node
python node.py --roles media

# Run a web interface node
python node.py --roles web

# Run a multi-role node
python node.py --roles system,web
```

### Task Role Requirements

Tasks in schedule.json can specify required roles:

```json
{
  "id": "video_stream",
  "type": "video",
  "required_role": "media",
  "config": { ... }
}
```

Only nodes with the matching role will pick up these tasks.

## Getting Started: How to Run a Node

Anyone can join the swarm by running a node.

#### Prerequisites

- `git`
- `python3`
- `docker`
- **Password-less Git Access:** Your machine must be able to `git push` to this repository without asking for a password. The recommended way is to set up authentication via SSH keys.

#### 1. Clone the Repository

```bash
git clone <your_repository_url>
cd shortlist
```

#### 2. Run a Basic Node

To start a node that participates in the swarm's coordination (but doesn't broadcast yet), simply run:

```bash
python3 node.py
```

The node will generate a unique ID, register itself in `roster.json`, and begin its lifecycle.

#### 3. Test the System Locally

The system comes with several renderers that work out of the box without external credentials:

```bash
python3 node.py
```

Once a node is running, you can access the different interfaces:

- **🎛️ Control Room**: http://localhost:8005 - **Primary interface** with real-time monitoring, governance integration, and shortlist editing
- **Dashboard**: http://localhost:8000 - Basic swarm activity and node status monitoring
- **Audio Stream**: http://localhost:8001 - Listen to TTS audio of the shortlist with web player
- **Video Stream**: http://localhost:8002 - Watch MP4 video with synchronized audio and clean text display
- **Web Interface**: http://localhost:8003 - Simple HTML view of shortlist content
- **Governance API**: http://localhost:8004 - Secure API for content management (requires setup)

#### 4. Enable External Integrations (Optional)

For production use with external services, you can provide credentials via environment variables:

**Example: Enabling the Telegram Bot**
```bash
export TELEGRAM_API_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="@your_channel_name"
python3 node.py
```

**🛡️ Enabling the Governance API**

For **demo/testing** (limited functionality):
```bash
export GIT_AUTH_TOKEN="test-token"
export GITHUB_REPO="your-username/your-repo"
export MAINTAINER_API_TOKEN="test-maintainer-123"
export CONTRIBUTOR_API_TOKEN="test-contributor-456"
python3 node.py
```

For **production** (full functionality):
```bash
export GIT_AUTH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"  # GitHub Personal Access Token
export GITHUB_REPO="your-username/shortlist"      # Your repository
export MAINTAINER_API_TOKEN="$(uuidgen)"          # Generate unique token
export CONTRIBUTOR_API_TOKEN="$(uuidgen)"         # Generate unique token
python3 node.py
```

**✅ What you'll see in the Control Room:**
- **Demo mode**: Status endpoints work, API operations show friendly errors
- **Production mode**: Full governance functionality with GitHub integration

> 📖 **For complete Governance API setup instructions, see [GOVERNANCE_SETUP.md](GOVERNANCE_SETUP.md)**

#### 5. Enable the Public Ledger (Optional)

To have your node contribute to the public log of swarm activities:

1.  Create a separate, empty GitHub repository (e.g., `shortlist-log`).
2.  Generate a new SSH key and add the **public key** as a **Deploy Key** (with write access) in the settings of your `shortlist-log` repository.
3.  Ensure the machine running the node is configured to use the corresponding **private key** for Git operations.
4.  Launch the node with the `LOG_REPO_URL` environment variable:

```bash
export LOG_REPO_URL="git@github.com:your-user/shortlist-log.git"
python3 node.py
```

--- 

## How to Interact with the Swarm

There are multiple ways to interact with and update the shortlist:

### 🔧 **Direct Git Method (Traditional)**
Modify the `shortlist.json` file and push the change to GitHub. The `watcher` function within the nodes will detect the change, and the swarm will automatically coordinate to update the broadcasts.

### 🛡️ **Governance API Method (Recommended for Production)**
Use the secure API endpoints for controlled access:

**Maintainer Access (Auto-merge):**
```bash
curl -X POST http://localhost:8004/v1/admin/shortlist \
  -H "Authorization: Bearer YOUR_MAINTAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": ["New Item 1", "New Item 2"]}'
```

**Contributor Access (Pull Request):**
```bash
curl -X POST http://localhost:8004/v1/proposals/shortlist \
  -H "Authorization: Bearer YOUR_CONTRIBUTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["Proposed Item"],
    "description": "Adding new trending topic"
  }'
```

### 📛 Remote Swarm Configuration

Shortlist supports dynamic, centralized configuration through `swarm_config.json`. This enables real-time tuning of the entire swarm's behavior without requiring node restarts.

#### Configuration Categories

- **Intervals**: Control timing of heartbeats, health checks, and loop cycles
- **Timeouts**: Define thresholds for node/task failure detection
- **Jitter**: Configure collision avoidance timing
- **Resilience**: Set retry policies and error handling behavior
- **Memory Limits**: Control resource usage boundaries
- **Feature Flags**: Toggle experimental features

#### Example Configuration

```json
{
  "log_level": "INFO",
  "intervals": {
    "node_heartbeat_seconds": 300,
    "task_heartbeat_seconds": 60
  },
  "timeouts": {
    "node_timeout_seconds": 900,
    "task_timeout_seconds": 180
  },
  "feature_flags": {
    "enable_auto_scaling": false,
    "strict_health_checks": true
  }
}
```

#### Common Use Cases

1. **Debug Mode**: Set `log_level` to `DEBUG` across the swarm
   ```json
   { "log_level": "DEBUG" }
   ```

2. **Performance Tuning**: Adjust timing intervals
   ```json
   {
     "intervals": {
       "idle_loop_seconds": 5,
       "git_sync_seconds": 15
     }
   }
   ```

3. **Network Issues**: Increase timeouts and retries
   ```json
   {
     "timeouts": {
       "git_operation_seconds": 60
     },
     "resilience": {
       "max_git_retries": 5
     }
   }
   ```

### 🚀 Event Notifications via Webhooks

Shortlist can notify external services about important system events through webhooks. This enables real-time integration with chat platforms, monitoring systems, or custom applications.

#### Supported Events

- `shortlist.updated`: Triggered when the content of shortlist.json changes
- `node.down`: *(Coming Soon)* Triggered when a node becomes unresponsive
- `node.up`: *(Coming Soon)* Triggered when a node recovers

#### Webhook Payload Example

```json
{
    "event": "shortlist.updated",
    "timestamp": "2025-09-28T21:05:11Z",
    "triggered_by": "git_commit:a1b2c3d4",
    "data": {
        "items": [
            "Latest announcement goes here",
            "Another important update"
        ]
    }
}
```

#### Integration Examples

**Slack Integration:**
```bash
# Create a Slack webhook
curl -X POST http://localhost:8004/v1/admin/webhooks \
  -H "Authorization: Bearer $MAINTAINER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/HERE",
    "event": "shortlist.updated",
    "description": "Notify #announcements channel"
  }'
```

**Custom Integration:**
```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    event = request.json["event"]
    data = request.json["data"]
    # Process the webhook payload
    return "", 200
```

### 🔒 Security & Governance

The Governance API implements a "Trust Circles" architecture:

- **🔑 Maintainer Circle**: Full access with immediate updates
- **👥 Contributor Circle**: Proposal-based access requiring review
- **📋 Audit Trail**: All changes tracked through GitHub's version control
- **🛡️ Branch Protection**: Configurable approval workflows
- **🤖 Automation**: Seamless integration with existing swarm infrastructure

## Scaling Architecture

For a complete overview of Shortlist's scaling model (roles, leases, sharding, and the swarm simulator), see SCALING_ARCHITECTURE.md.

## License

## Structured Logging System

The Shortlist system uses a comprehensive structured logging system across all components:

### Key Features

- **JSON-formatted Logs**: All logs are output in JSON format for better parsing and analysis
- **Context-aware Logging**: Component-specific and operation-specific context is automatically included
- **Performance Tracking**: Automatic timing for operations and function execution
- **Error Context**: Rich error information with type, message, and stack traces when needed
- **Request Tracing**: HTTP request logging with path, client info, and timing
- **Component Status**: Consistent startup/shutdown logging across all components

### Log Format Example

```json
{
    "timestamp": "2025-09-28T19:57:31.123Z",
    "level": "INFO",
    "message": "Request completed",
    "logger": "admin_ui_renderer",
    "component_type": "renderer",
    "renderer_type": "admin_ui",
    "path": "/api/status",
    "method": "GET",
    "remote_addr": "192.168.1.100",
    "status_code": 200,
    "execution_time": 0.123
}
```

### Component Logging

Each component in the system includes structured logging:

- **Node Core**: Task management, assignment tracking, and state changes
- **Admin UI**: User interactions and API proxy operations
- **Governance API**: Authentication, git operations, and PR management
- **Audio Renderer**: TTS synthesis and stream management
- **Video Renderer**: Media generation and streaming
- **Dashboard**: System state monitoring and data aggregation
- **Governor**: Trigger evaluation and schedule management
- **Healer**: Health checks and zombie task cleanup

### Log Files

Component logs are stored in `/app/data/` with component-specific files:
- `admin_ui.log`: Control room interface logs
- `api.log`: Governance API logs
- `audio.log`: Audio renderer logs
- `dashboard.log`: Status dashboard logs
- `governor.log`: Governor component logs
- `healer.log`: Healer component logs
- `text.log`: Text renderer logs
- `video.log`: Video renderer logs

---

### ⚡ Intelligent Content Caching

Shortlist now implements an intelligent caching system for rendered content, dramatically improving performance and resource utilization:

- **Per-Item Caching**: Each item in shortlist.json is individually cached after rendering
- **Content-Based Invalidation**: Cache entries are invalidated only when content actually changes
- **Automatic Cache Management**: Old or unused entries are automatically cleaned up
- **Resource-Aware**: Cache maintains minimum free space and removes oldest entries when needed

Benefits:
- **Faster Updates**: Changes to shortlist.json are reflected almost instantly
- **Resource Efficiency**: Avoid re-rendering unchanged content
- **Reduced Load**: Significantly lower CPU and memory usage during updates

Cache Configuration (in task_config.json):
```json
{
  "cache": {
    "max_age_days": 30,
    "min_free_space_mb": 1000,
    "cleanup_interval_hours": 24
  }
}
```

### 🔄 Parallel Processing with Task Sharding

Shortlist supports automatic task sharding for parallel processing of large workloads:

#### Sharding Configuration

```json
{
  "id": "video_broadcast",
  "type": "video",
  "sharding": {
    "enabled": true,
    "items_per_shard": 5,
    "min_items_for_sharding": 10,
    "max_shards": 4
  }
}
```

#### How It Works

1. **Task Splitting**: The governor automatically splits large tasks into multiple shards
2. **Parallel Processing**: Multiple nodes process shards simultaneously
3. **Result Combination**: A combiner task assembles the final output

Benefits:
- **Faster Processing**: Process large workloads in parallel
- **Better Resource Usage**: Distribute work across the swarm
- **Automatic Scaling**: Number of shards adapts to workload size
- **Flexible Configuration**: Control shard size and limits per task

### 🤖 Autonomous Agents

Shortlist can be enriched by autonomous agents - external processes that interact with the governance API to propose or manage content automatically. These agents operate independently but integrate seamlessly with Shortlist's governance system.

### Available Agents

#### 📰 RSS Curator
The RSS Curator agent monitors configured RSS feeds and automatically proposes new articles to the shortlist when they match specific keywords. It's perfect for keeping your shortlist updated with the latest relevant content from trusted sources.

**Features:**
- 🔍 Keyword-based article filtering
- 📅 Age-based filtering (skip older articles)
- 🎯 Multiple feed support with per-feed configuration
- 📊 Structured logging and monitoring
- 🔄 Automatic duplicate detection

**Setup:**

1. Navigate to the agent directory:
   ```bash
   cd agents/rss_curator
   ```

2. Configure your feeds in `config.json`:
   ```json
   {
     "feeds": [
       {
         "name": "Tech News",
         "url": "https://example.com/feed.xml",
         "keywords": ["AI", "cloud", "security"],
         "max_age_days": 2
       }
     ]
   }
   ```

3. Set up your environment:
   ```bash
   export CONTRIBUTOR_API_TOKEN="your-token-here"
   ```

4. Run the agent:
   ```bash
   # Direct execution
   python curator.py
   
   # Or using Docker
   docker build -t rss-curator .
   docker run -e CONTRIBUTOR_API_TOKEN -v $PWD/data:/app/data rss-curator
   ```

The agent will start monitoring your configured feeds and propose new articles that match your criteria through Shortlist's governance API.

---

This project is licensed under the MIT License.
