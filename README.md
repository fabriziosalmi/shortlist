# Shortlist: A Decentralized Broadcasting Swarm

**Shortlist** is a decentralized, resilient, and transparent system that allows a community to collectively broadcast a shared message—a "shortlist" of important topics—across multiple platforms simultaneously.

It operates as a **leaderless swarm** of independent nodes that coordinate their actions using a Git repository as their single source of truth and coordination backend. No central server, no single point of failure.

---

## Core Concepts

This project is an experiment in decentralized collaboration. The key principles are:

- **Decentralization:** There is no central orchestrator. Any machine that can run the `node.py` script can join the swarm and contribute to the broadcasting effort.
- **Resilience:** The swarm is self-healing. If a node responsible for a broadcast task dies, another node will automatically detect the failure and take over the task.
- **Transparency:** The entire state of the swarm—who is active, what tasks are being performed, and by whom—is publicly visible and auditable through the Git history of this repository.
- **Git as a Backend:** Instead of complex coordination services like Zookeeper or etcd, the swarm uses Git itself as a distributed lock and state machine, making the system surprisingly simple and robust.

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

### Node Self-Awareness
Every node now monitors its own performance (CPU, memory) and reports it in real-time, transforming the swarm into a sensory system. This data is crucial for the Governor to make informed decisions.

### The Governor (`governor`)
A strategic 'brain' with **Priority -2** that dynamically adapts the swarm's tasks (by modifying `schedule.json`) based on rules defined in `triggers.json`. This allows the swarm to react to temporal events or changes in overall health status.

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

### 🔒 **Security & Governance**

The Governance API implements a "Trust Circles" architecture:

- **🔑 Maintainer Circle**: Full access with immediate updates
- **👥 Contributor Circle**: Proposal-based access requiring review
- **📋 Audit Trail**: All changes tracked through GitHub's version control
- **🛡️ Branch Protection**: Configurable approval workflows
- **🤖 Automation**: Seamless integration with existing swarm infrastructure

## License

This project is licensed under the MIT License.
