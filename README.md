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
- `schedule.json`: Defines the broadcasting "tasks" that the swarm needs to perform (e.g., text posts, audio stream, video generation, web interface, dashboard).
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

**Currently Available Renderers:**

- **Dashboard Renderer** (`dashboard`) - Port 8000: Real-time swarm status dashboard showing active nodes, task assignments, and system health
- **Audio Renderer** (`audio`) - Port 8001: Text-to-Speech audio stream with web player interface
- **Video Renderer** (`video`) - Port 8002: MP4 video generation with synchronized TTS audio and visual text display
- **Web Renderer** (`web`) - Port 8003: Simple HTML interface displaying the shortlist content
- **Text Renderer** (`text`) - Telegram bot integration for text-based social media posting

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

Then open these URLs in your browser:
- Dashboard: http://localhost:8000
- Audio: http://localhost:8001
- Video: http://localhost:8002
- Web: http://localhost:8003

The system will automatically start generating content from `shortlist.json` and you can see the swarm coordination in real-time!

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

- **Dashboard**: http://localhost:8000 - Monitor swarm activity and node status
- **Audio Stream**: http://localhost:8001 - Listen to TTS audio of the shortlist
- **Video Stream**: http://localhost:8002 - Watch video with synchronized audio and text
- **Web Interface**: http://localhost:8003 - View shortlist in simple HTML format

#### 4. Enable External Integrations (Optional)

For production use with external services, you can provide credentials via environment variables:

**Example: Enabling the Telegram Bot**
```bash
export TELEGRAM_API_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="@your_channel_name"
python3 node.py
```

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

Once the swarm is active, the only way to interact with it is to **modify the `shortlist.json` file and push the change to GitHub.**

The `watcher` function within the nodes will detect the change, and the swarm will automatically coordinate to update the broadcasts.

## License

This project is licensed under the MIT License.
