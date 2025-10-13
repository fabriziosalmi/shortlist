# 🚀 Shortlist: Decentralized Broadcasting Swarm

**Shortlist** is a resilient, decentralized broadcasting system that uses **Git as a coordination backend** to manage a swarm of autonomous nodes. No central server, no single point of failure.

[![Deploy Status](https://img.shields.io/badge/deploy-ready-brightgreen)](https://github.com/fabriziosalmi/shortlist) [![Geographic Support](https://img.shields.io/badge/geographic-multi--region-blue)](#-geographic-distribution) [![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## 🎯 Quick Start

Want to see it in action immediately?

```bash
git clone https://github.com/fabriziosalmi/shortlist.git
cd shortlist
python3 node.py
```

**🎛️ Primary Interface**: Open http://localhost:8005 (Control Room)

The system automatically starts generating content from `shortlist.json` and you can monitor the entire swarm in real-time!

## 📋 Table of Contents

- [🎯 Quick Start](#-quick-start)
- [🏗️ Core Architecture](#️-core-architecture)
- [🎛️ Available Interfaces](#️-available-interfaces)
- [⚙️ System Components](#️-system-components)
- [🌍 Geographic Distribution](#-geographic-distribution)
- [🔧 Configuration](#-configuration)
- [📚 Advanced Features](#-advanced-features)
- [🚀 Deployment](#-deployment)
- [📖 Documentation](#-documentation)

---

## 🏗️ Core Architecture

### The Innovation: Git as Coordination Backend

Instead of complex systems like Zookeeper or etcd, Shortlist uses **Git itself** as a distributed coordination mechanism:

- **📄 State Files**: `shortlist.json`, `roster.json`, `schedule.json`, `assignments.json`
- **🔄 Atomic Operations**: Git's commit atomicity ensures conflict-free task claiming
- **🌐 Distributed by Design**: Every node has a complete copy of the coordination state
- **📜 Full Auditability**: Every state change is permanently recorded in Git history

### Key Principles

- **🔗 Decentralized**: No central orchestrator—any machine can join the swarm
- **🛡️ Self-Healing**: Automatic node failure detection and task recovery
- **👁️ Transparent**: All operations visible and auditable through Git
- **⚡ Efficient**: Intelligent batching and caching minimize resource usage

---

## 🎛️ Available Interfaces

### **🎛️ Control Room** (Port 8005) - **PRIMARY INTERFACE**
**Complete monitoring, governance, and editing dashboard**
- 🌐 Real-time swarm monitoring with live node and task status
- 📝 Advanced shortlist editor (JSON and text formats)
- 🛡️ Governance API integration with intelligent error handling
- ⌨️ Keyboard shortcuts (Ctrl+R, Ctrl+S) and auto-refresh

### **Core Interfaces**
| Interface | Port | Description |
|-----------|------|-------------|
| 🛡️ **Governance API** | 8004 | Secure API for content management with tiered access |
| 📊 **Dashboard** | 8000 | Basic swarm status monitoring |
| 🎵 **Audio Stream** | 8001 | Text-to-Speech audio with web player |
| 🎬 **Video Stream** | 8002 | MP4 video with synchronized TTS audio |
| 🌐 **Web Interface** | 8003 | Simple HTML content display |

### **Specialized Services**
- **📱 Telegram Bot**: Social media posting and notifications
- **🚀 Live Streamer**: 24/7 RTMP streaming to YouTube/Twitch
- **📊 Metrics Exporter**: System performance and health metrics
- **💾 Archiver**: Automated backup and disaster recovery

---

## ⚙️ System Components

### 🧠 **Autonomous Core Systems**

**🧠 Governor** (Priority -2)
- Strategic "brain" that adapts swarm tasks based on triggers
- Quorum-based decision making for safe operations
- Automatic scaling and resource optimization

**🩹 Healer** (Priority -1)
- "Immune system" that corrects state inconsistencies
- Zombie task cleanup and orphan detection
- Continuous health monitoring and recovery

### 🎯 **Node State Machine**

Each node operates as a state machine with three primary states:

1. **`IDLE`**: Scanning for available tasks or orphaned assignments
2. **`ATTEMPT_CLAIM`**: Racing with other nodes to claim a task (with jitter)
3. **`ACTIVE`**: Running the assigned renderer and sending heartbeats

### 🏷️ **Task Priority System**

Tasks are assigned by priority (lower number = higher priority):

```
-2: Governor (strategic decisions)
-1: Healer (maintenance and recovery)
 0: Governance API (secure content management)
 1: Control Room (primary interface)
 2: Dashboard (status monitoring)
 3: Social Media (Telegram, etc.)
 4: Audio/Video (media generation)
 5: Web Interface (content display)
```

---

## 🌍 Geographic Distribution

**NEW**: Multi-region deployment with automatic failover and conflict resolution.

### Quick Regional Setup

```bash
# Single region (default)
python node.py

# Specify region
python node.py --region eu-west

# Enable full geographic sharding
python node.py --enable-geo-sharding --region us-east
```

### Regional Features

- **🗺️ Multi-Region Deployment**: Deploy across continents with local coordination
- **⚖️ Smart Conflict Resolution**: Semantic merging for content, priority-based for critical ops
- **📍 Regional Compliance**: GDPR-compliant data residency
- **🔄 Cross-Region Sync**: Eventual consistency with configurable lag limits
- **🎯 Regional Task Ownership**: Route specific tasks to appropriate regions

**📖 Full Guide**: See [GEOGRAPHIC_DISTRIBUTION.md](GEOGRAPHIC_DISTRIBUTION.md)

---

## 🔧 Configuration

### Essential Files

| File | Purpose | Edit? |
|------|---------|-------|
| `shortlist.json` | **Content to broadcast** | ✅ **Edit this** |
| `schedule.json` | Task definitions and priorities | ⚙️ Configure |
| `swarm_config.json` | Global swarm behavior settings | ⚙️ Configure |
| `geographic_config.json` | Multi-region settings | 🌍 Regional |
| `roster.json` | Active nodes (auto-managed) | ❌ **Auto** |
| `assignments.json` | Task assignments (auto-managed) | ❌ **Auto** |

### Content Management

**Simple Format**:
```json
{
  "items": [
    "Your first announcement",
    "Another important update"
  ]
}
```

**Advanced Format with Scheduling**:
```json
{
  "items": [
    {
      "id": "morning_greeting",
      "content": "Good morning!",
      "schedule": "0 8 * * 1-5"
    },
    {
      "id": "weekend_special",
      "content": "Weekend edition!",
      "schedule": "0 10 * * 6,0"
    }
  ]
}
```

**Dynamic Templates with Data**:
```json
{
  "data": {
    "company": "TechCorp",
    "quarter": "Q4 2025"
  },
  "items": [
    {
      "content": "{{ company }} {{ quarter }} Update"
    }
  ]
}
```

---

## 📚 Advanced Features

### 🤖 **Autonomous Agents**
External processes that interact with the governance API:
- **📰 RSS Curator**: Automatically proposes relevant articles
- **📊 Metrics Agent**: System performance monitoring
- **🔍 Content Analyzer**: Automated content quality checks

### ⚡ **Performance Optimizations**
- **Intelligent Caching**: Content-based invalidation for faster updates
- **Batched Operations**: Reduced Git write traffic by 97%
- **Task Sharding**: Parallel processing for large workloads
- **Lease Protocol**: Efficient task coordination with minimal overhead

### 🔒 **Security & Governance**
- **🎫 Tiered Access Control**: Maintainer and Contributor roles
- **🔄 Automated Pull Requests**: Secure content update workflow
- **📋 Complete Audit Trail**: Every change tracked in Git history
- **🛡️ Branch Protection**: Configurable approval workflows

### 🎯 **Node Specialization**
```bash
# System tasks only
python node.py --roles system

# Media processing
python node.py --roles media

# Multiple roles
python node.py --roles system,web,broadcaster
```

---

## 🚀 Deployment

### Prerequisites
- **Git** with passwordless push access
- **Python 3.8+**
- **Docker** (for renderers)

### Production Deployment

**Single Region**:
```bash
git clone <your_repository_url>
cd shortlist
python3 node.py
```

**Multi-Region**:
```bash
# US East (Primary)
python3 node.py --enable-geo-sharding --region us-east --roles system,web

# Europe West (Compliance)
python3 node.py --enable-geo-sharding --region eu-west --roles media,broadcaster

# Asia Pacific (Edge)
python3 node.py --enable-geo-sharding --region asia-pacific --roles web
```

### Environment Variables

```bash
# Region selection
export SHORTLIST_REGION=eu-west

# Governance API (production)
export GIT_AUTH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
export GITHUB_REPO="your-username/shortlist"
export MAINTAINER_API_TOKEN="$(uuidgen)"
export CONTRIBUTOR_API_TOKEN="$(uuidgen)"

# External integrations
export TELEGRAM_API_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="@your_channel"
```

### Docker Deployment

```bash
# Build and run
docker build -t shortlist-node .
docker run -e SHORTLIST_REGION=us-east \
           -v $(pwd):/app \
           shortlist-node

# Kubernetes
kubectl apply -f deployment/shortlist-swarm.yaml
```

---

## 📖 Documentation

### Core Documentation
- **[SCALING_ARCHITECTURE.md](SCALING_ARCHITECTURE.md)**: Roles, leases, sharding, and swarm simulation
- **[GEOGRAPHIC_DISTRIBUTION.md](GEOGRAPHIC_DISTRIBUTION.md)**: Multi-region deployment guide
- **[GOVERNANCE_SETUP.md](GOVERNANCE_SETUP.md)**: Secure API configuration

### Feature Guides
- **[FEATURES.md](FEATURES.md)**: Complete features deep dive
- **[DEPLOYMENT.md](DEPLOYMENT.md)**: Production deployment guide
- **[SCHEDULING.md](SCHEDULING.md)**: Time-based content scheduling
- **[PLUGINS_DEVELOPMENT.md](renderers/video/PLUGINS_DEVELOPMENT.md)**: Video renderer plugins

### Operational
- **[docs/](docs/)**: Detailed operational guides and reviews
- **[tools/swarm_simulator.py](tools/swarm_simulator.py)**: Test system behavior under various conditions

---

## 🔧 Development & Contributing

### Running Tests
```bash
# System simulation
python tools/swarm_simulator.py --nodes 5 --duration 300

# Health checks
curl http://localhost:8000/health

# API documentation
open http://localhost:8004/docs
```

### System Health
```bash
# Monitor logs
tail -f output/*.log

# Regional statistics
python -c "from utils.geographic import get_geographic_manager; print(get_geographic_manager().get_regional_statistics())"

# Performance metrics
curl http://localhost:8005/api/metrics
```

---

## 🏆 Why Shortlist?

- **🎯 Simple but Powerful**: Complex coordination made simple through Git
- **🔧 Production Ready**: Used for real-world broadcasting with enterprise-grade reliability
- **🌍 Globally Scalable**: Multi-region support with intelligent conflict resolution
- **🛡️ Secure by Design**: Comprehensive audit trail and tiered access control
- **⚡ High Performance**: Optimized for minimal resource usage and maximum throughput
- **🚀 Easy to Deploy**: From laptop to global infrastructure in minutes

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**🚀 Ready to broadcast?** Start with `python node.py` and open http://localhost:8005

**🌍 Need multi-region?** Check out [GEOGRAPHIC_DISTRIBUTION.md](GEOGRAPHIC_DISTRIBUTION.md)

**🤝 Need help?** See our [documentation](docs/) or create an [issue](https://github.com/fab/shortlist/issues)
