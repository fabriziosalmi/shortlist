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
- `schedule.json`: Defines the broadcasting "tasks" that the swarm needs to perform (e.g., run a video stream, run an audio stream).
- `assignments.json`: A real-time map of which node is currently performing which task. This is the swarm's coordination "whiteboard".

#### 2. The Node (`node.py`)

This is the heart of the system. Each running instance of `node.py` is an independent member of the swarm. Each node operates as a state machine:

- **`IDLE`**: The node is alive and looking for work. It scans the `schedule.json` and `assignments.json` to find free or "orphan" tasks (tasks whose controlling node has gone silent).
- **`ATTEMPT_CLAIM`**: When a free task is found, the node waits a random "jitter" period to avoid conflicts with other nodes. It then attempts to "claim" the task by writing its ID to `assignments.json` and pushing the change. It uses Git's atomic nature to ensure only one node can claim a task at a time.
- **`ACTIVE`**: Once a task is claimed, the node enters the `ACTIVE` state. It launches the appropriate **Renderer** and continuously sends a "task heartbeat" to `assignments.json` to signal that it is still alive and in control of the task.

If a node crashes, its heartbeats stop, and the task it was performing becomes "orphan", ready to be claimed by another `IDLE` node.

#### 3. The Renderers

Renderers are the "muscles" of the swarm. They are containerized applications (managed by Docker) that perform the actual broadcasting.

- Each renderer is specialized for a task type (e.g., `text`, `audio`).
- The `node.py` script orchestrates these renderers, starting and stopping their containers as needed.
- This design keeps dependencies isolated and allows for new broadcast platforms to be added easily.

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

#### 3. Enable Renderers (Optional)

To allow your node to perform broadcast tasks, you must provide it with the necessary credentials via environment variables before running it.

**Example: Enabling the Telegram Bot**
```bash
export TELEGRAM_API_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="@your_channel_name"
python3 node.py
```

**Example: Enabling the Icecast Audio Stream**
```bash
export ICECAST_HOST="your_icecast_host.com"
export ICECAST_PORT="8000"
export ICECAST_PASSWORD="your_password"
export ICECAST_MOUNT="/live"
python3 node.py
```

#### 4. Enable the Public Ledger (Optional)

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
