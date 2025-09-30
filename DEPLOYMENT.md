# 🚀 Shortlist Deployment Guide

Complete guide for deploying Shortlist in various environments, from development to enterprise production.

## 📋 Table of Contents

- [🎯 Quick Deployment](#-quick-deployment)
- [🔧 Prerequisites](#-prerequisites)
- [🏠 Local Development](#-local-development)
- [☁️ Cloud Deployment](#️-cloud-deployment)
- [🌍 Multi-Region Setup](#-multi-region-setup)
- [🐳 Docker & Kubernetes](#-docker--kubernetes)
- [⚙️ Configuration Management](#️-configuration-management)
- [📊 Monitoring Setup](#-monitoring-setup)
- [🔒 Security Hardening](#-security-hardening)

---

## 🎯 Quick Deployment

### Fastest Start (Development)

```bash
git clone <your_repository_url>
cd shortlist
python3 node.py
```

**That's it!** Open http://localhost:8005 to access the Control Room.

### Production Ready (Single Command)

```bash
# Set environment variables
export GIT_AUTH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
export GITHUB_REPO="your-org/shortlist"
export MAINTAINER_API_TOKEN="$(uuidgen)"

# Run with production settings
python3 node.py --region us-east
```

---

## 🔧 Prerequisites

### Required Software

| Component | Version | Purpose |
|-----------|---------|---------|
| **Git** | 2.20+ | Coordination backend |
| **Python** | 3.8+ | Node runtime |
| **Docker** | 20.0+ | Renderer containers |

### System Requirements

**Minimum**:
- CPU: 1 core
- RAM: 512MB
- Disk: 1GB
- Network: 10 Mbps

**Recommended**:
- CPU: 2+ cores
- RAM: 2GB+
- Disk: 10GB+ SSD
- Network: 100 Mbps

**Production**:
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 100GB+ SSD
- Network: 1 Gbps

### Git Authentication Setup

**SSH Keys (Recommended)**:
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "shortlist@your-domain.com"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy to GitHub Settings > SSH Keys

# Test authentication
ssh -T git@github.com
```

**Personal Access Token**:
```bash
# Create token at: https://github.com/settings/tokens
# Required scopes: repo, workflow

export GIT_AUTH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
```

---

## 🏠 Local Development

### Development Environment Setup

```bash
# Clone repository
git clone git@github.com:your-org/shortlist.git
cd shortlist

# Create virtual environment (optional)
python3 -m venv venv
source venv/bin/activate

# Install dependencies (if any)
pip install -r requirements.txt

# Start development node
python3 node.py
```

### Development Configuration

**Minimal `shortlist.json`**:
```json
{
  "items": [
    "Development test message",
    "Another test announcement"
  ]
}
```

**Development Environment Variables**:
```bash
# Use test tokens for development
export GIT_AUTH_TOKEN="test-token"
export GITHUB_REPO="test/repo"
export MAINTAINER_API_TOKEN="test-maintainer-123"
export CONTRIBUTOR_API_TOKEN="test-contributor-456"
```

### Multiple Local Nodes

```bash
# Terminal 1 - Primary node
python3 node.py --region us-east

# Terminal 2 - Secondary node
python3 node.py --region us-east

# Terminal 3 - EU node
python3 node.py --region eu-west
```

---

## ☁️ Cloud Deployment

### AWS Deployment

**EC2 Instance Setup**:
```bash
# Launch Ubuntu 22.04 LTS instance
# Instance type: t3.medium or larger

# Install dependencies
sudo apt update
sudo apt install -y git python3 python3-pip docker.io
sudo usermod -a -G docker ubuntu

# Clone and setup
git clone git@github.com:your-org/shortlist.git
cd shortlist

# Configure environment
echo 'export GIT_AUTH_TOKEN="your-token"' >> ~/.bashrc
echo 'export GITHUB_REPO="your-org/shortlist"' >> ~/.bashrc
source ~/.bashrc

# Start service
python3 node.py --region us-east
```

**Systemd Service**:
```ini
# /etc/systemd/system/shortlist.service
[Unit]
Description=Shortlist Node
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/shortlist
Environment=GIT_AUTH_TOKEN=your-token
Environment=GITHUB_REPO=your-org/shortlist
Environment=SHORTLIST_REGION=us-east
ExecStart=/usr/bin/python3 node.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable shortlist
sudo systemctl start shortlist
sudo systemctl status shortlist
```

### Google Cloud Platform

**Compute Engine Setup**:
```bash
# Create instance
gcloud compute instances create shortlist-node \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB

# SSH and setup
gcloud compute ssh shortlist-node --zone=us-central1-a

# Install and configure (same as AWS)
```

### Azure Deployment

**Virtual Machine Setup**:
```bash
# Create VM
az vm create \
  --resource-group shortlist-rg \
  --name shortlist-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys

# Connect and setup
az vm run-command invoke \
  --resource-group shortlist-rg \
  --name shortlist-vm \
  --command-id RunShellScript \
  --scripts "$(cat setup-script.sh)"
```

---

## 🌍 Multi-Region Setup

### Geographic Distribution Architecture

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    US-EAST      │  │    EU-WEST      │  │  ASIA-PACIFIC   │
│   (Primary)     │  │  (Compliance)   │  │     (Edge)      │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ • Governor      │  │ • GDPR Tasks    │  │ • Regional UI   │
│ • Healer        │  │ • EU Media      │  │ • Local Cache   │
│ • Global API    │  │ • Compliance    │  │ • Edge Delivery │
│ • Coordination  │  │ • Regional API  │  │ • Localization  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Regional Configuration

**Create `geographic_config.json`**:
```json
{
  "geographic_sharding": {
    "enabled": true,
    "default_region": "us-east"
  },
  "regions": {
    "us-east": {
      "name": "US East (Primary)",
      "priority": 1,
      "weight": 2,
      "timezone": "America/New_York",
      "git_repo": "git@github.com:org/shortlist-us.git"
    },
    "eu-west": {
      "name": "Europe West",
      "priority": 2,
      "weight": 1,
      "timezone": "Europe/London",
      "git_repo": "git@github.com:org/shortlist-eu.git"
    },
    "asia-pacific": {
      "name": "Asia Pacific",
      "priority": 3,
      "weight": 1,
      "timezone": "Asia/Tokyo",
      "git_repo": "git@github.com:org/shortlist-apac.git"
    }
  },
  "regional_ownership": {
    "us-east": ["global_announcements", "governance_api"],
    "eu-west": ["gdpr_notices", "eu_compliance"],
    "asia-pacific": ["regional_events", "local_updates"]
  }
}
```

### Regional Deployment Commands

**US East (Primary Coordinator)**:
```bash
python3 node.py \
  --enable-geo-sharding \
  --region us-east \
  --roles system,web
```

**EU West (Compliance)**:
```bash
python3 node.py \
  --enable-geo-sharding \
  --region eu-west \
  --roles media,broadcaster
```

**Asia Pacific (Edge)**:
```bash
python3 node.py \
  --enable-geo-sharding \
  --region asia-pacific \
  --roles web,broadcaster
```

---

## 🐳 Docker & Kubernetes

### Docker Deployment

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy application
COPY . .

# Set up git configuration
RUN git config --global user.email "shortlist@docker.local" && \
    git config --global user.name "Shortlist Docker"

# Expose ports
EXPOSE 8000-8010

# Start node
CMD ["python3", "node.py"]
```

**Docker Compose**:
```yaml
version: '3.8'

services:
  shortlist-us:
    build: .
    environment:
      - SHORTLIST_REGION=us-east
      - GIT_AUTH_TOKEN=${GIT_AUTH_TOKEN}
      - GITHUB_REPO=${GITHUB_REPO}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/app/data
    ports:
      - "8000-8010:8000-8010"
    restart: unless-stopped

  shortlist-eu:
    build: .
    environment:
      - SHORTLIST_REGION=eu-west
      - GIT_AUTH_TOKEN=${GIT_AUTH_TOKEN}
      - GITHUB_REPO=${GITHUB_REPO}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data-eu:/app/data
    ports:
      - "8020-8030:8000-8010"
    restart: unless-stopped
```

### Kubernetes Deployment

**Namespace**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: shortlist
```

**ConfigMap**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: shortlist-config
  namespace: shortlist
data:
  geographic_config.json: |
    {
      "geographic_sharding": {
        "enabled": true,
        "default_region": "us-east"
      },
      "regions": {
        "us-east": {"priority": 1, "weight": 2},
        "eu-west": {"priority": 2, "weight": 1}
      }
    }
```

**Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shortlist-us-east
  namespace: shortlist
spec:
  replicas: 2
  selector:
    matchLabels:
      app: shortlist
      region: us-east
  template:
    metadata:
      labels:
        app: shortlist
        region: us-east
    spec:
      containers:
      - name: shortlist
        image: shortlist:latest
        env:
        - name: SHORTLIST_REGION
          value: "us-east"
        - name: GIT_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: git-credentials
              key: token
        - name: GITHUB_REPO
          value: "your-org/shortlist"
        ports:
        - containerPort: 8000
        - containerPort: 8005
        volumeMounts:
        - name: config
          mountPath: /app/geographic_config.json
          subPath: geographic_config.json
        - name: docker-sock
          mountPath: /var/run/docker.sock
      volumes:
      - name: config
        configMap:
          name: shortlist-config
      - name: docker-sock
        hostPath:
          path: /var/run/docker.sock
```

**Service**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: shortlist-control-room
  namespace: shortlist
spec:
  selector:
    app: shortlist
  ports:
  - name: control-room
    port: 8005
    targetPort: 8005
  - name: dashboard
    port: 8000
    targetPort: 8000
  type: LoadBalancer
```

---

## ⚙️ Configuration Management

### Environment-Specific Configs

**Development (`dev.env`)**:
```bash
SHORTLIST_REGION=development
GIT_AUTH_TOKEN=test-token
GITHUB_REPO=test/repo
MAINTAINER_API_TOKEN=dev-maintainer
CONTRIBUTOR_API_TOKEN=dev-contributor
LOG_LEVEL=DEBUG
```

**Staging (`staging.env`)**:
```bash
SHORTLIST_REGION=us-east
GIT_AUTH_TOKEN=ghp_staging_token
GITHUB_REPO=your-org/shortlist-staging
MAINTAINER_API_TOKEN=staging-maintainer
CONTRIBUTOR_API_TOKEN=staging-contributor
LOG_LEVEL=INFO
```

**Production (`prod.env`)**:
```bash
SHORTLIST_REGION=us-east
GIT_AUTH_TOKEN=ghp_production_token
GITHUB_REPO=your-org/shortlist
MAINTAINER_API_TOKEN=$(uuidgen)
CONTRIBUTOR_API_TOKEN=$(uuidgen)
LOG_LEVEL=WARNING
```

### Secrets Management

**AWS Secrets Manager**:
```bash
# Store secrets
aws secretsmanager create-secret \
  --name shortlist/production \
  --secret-string '{
    "GIT_AUTH_TOKEN": "ghp_xxxxxxxxxxxxxxxxxxxx",
    "MAINTAINER_API_TOKEN": "uuid-here",
    "CONTRIBUTOR_API_TOKEN": "uuid-here"
  }'

# Retrieve in startup script
SECRET=$(aws secretsmanager get-secret-value \
  --secret-id shortlist/production \
  --query SecretString --output text)

export GIT_AUTH_TOKEN=$(echo $SECRET | jq -r .GIT_AUTH_TOKEN)
```

**Kubernetes Secrets**:
```bash
# Create secret
kubectl create secret generic git-credentials \
  --from-literal=token=ghp_xxxxxxxxxxxxxxxxxxxx \
  --namespace=shortlist

# Use in deployment (see K8s example above)
```

---

## 📊 Monitoring Setup

### Logging Infrastructure

**Centralized Logging with ELK Stack**:
```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  elasticsearch:
    image: elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"

  kibana:
    image: kibana:8.5.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

  logstash:
    image: logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch
```

**Logstash Configuration**:
```ruby
# logstash.conf
input {
  file {
    path => "/app/output/*.log"
    start_position => "beginning"
    codec => "json"
  }
}

filter {
  if [logger] == "node" {
    mutate {
      add_tag => ["node"]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "shortlist-%{+YYYY.MM.dd}"
  }
}
```

### Metrics Collection

**Prometheus Configuration**:
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'shortlist'
    static_configs:
      - targets: ['localhost:8000', 'localhost:8005']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

**Grafana Dashboard**:
```json
{
  "dashboard": {
    "title": "Shortlist Swarm Metrics",
    "panels": [
      {
        "title": "Active Nodes",
        "type": "stat",
        "targets": [
          {
            "expr": "shortlist_active_nodes",
            "legendFormat": "Nodes"
          }
        ]
      },
      {
        "title": "Task Distribution",
        "type": "piechart",
        "targets": [
          {
            "expr": "shortlist_tasks_by_type",
            "legendFormat": "{{type}}"
          }
        ]
      }
    ]
  }
}
```

### Health Checks

**Application Health Endpoints**:
```bash
# Node health
curl http://localhost:8005/health

# Individual renderer health
curl http://localhost:8000/health  # Dashboard
curl http://localhost:8001/health  # Audio
curl http://localhost:8002/health  # Video
```

**Load Balancer Health Checks**:
```yaml
# AWS ALB Target Group
HealthCheckPath: /health
HealthCheckPort: 8005
HealthCheckProtocol: HTTP
HealthCheckIntervalSeconds: 30
HealthyThresholdCount: 2
UnhealthyThresholdCount: 3
```

---

## 🔒 Security Hardening

### Network Security

**Firewall Rules**:
```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8000:8010/tcp  # Shortlist services
sudo ufw enable

# iptables
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000:8010 -j ACCEPT
iptables -A INPUT -j DROP
```

**TLS/SSL Configuration**:
```nginx
# nginx reverse proxy
server {
    listen 443 ssl http2;
    server_name shortlist.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/shortlist.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/shortlist.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8005;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Access Control

**API Rate Limiting**:
```python
# Add to governance API
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

@app.route('/v1/admin/shortlist')
@limiter.limit("10 per minute")
def admin_shortlist():
    pass
```

**IP Whitelisting**:
```bash
# Environment variable
export ALLOWED_IPS="192.168.1.0/24,10.0.0.0/8"

# In application
ALLOWED_IPS = os.getenv('ALLOWED_IPS', '').split(',')
```

### Secrets Rotation

**Automated Token Rotation**:
```bash
#!/bin/bash
# rotate-tokens.sh

# Generate new tokens
NEW_MAINTAINER_TOKEN=$(uuidgen)
NEW_CONTRIBUTOR_TOKEN=$(uuidgen)

# Update secrets
aws secretsmanager update-secret \
  --secret-id shortlist/production \
  --secret-string "{
    \"MAINTAINER_API_TOKEN\": \"$NEW_MAINTAINER_TOKEN\",
    \"CONTRIBUTOR_API_TOKEN\": \"$NEW_CONTRIBUTOR_TOKEN\"
  }"

# Restart services
kubectl rollout restart deployment/shortlist-us-east
```

---

## 🎯 Production Checklist

### Pre-Deployment

- [ ] **Git Authentication**: SSH keys or PAT configured
- [ ] **Secrets Management**: All tokens stored securely
- [ ] **Monitoring**: Logging and metrics collection setup
- [ ] **Backups**: Repository and data backup strategy
- [ ] **DNS**: Domain names and SSL certificates
- [ ] **Firewall**: Network security rules configured

### Post-Deployment

- [ ] **Health Checks**: All endpoints responding correctly
- [ ] **Functionality**: Test content updates end-to-end
- [ ] **Performance**: Monitor resource usage and response times
- [ ] **Alerts**: Set up monitoring alerts and notifications
- [ ] **Documentation**: Update runbooks and contact information
- [ ] **Disaster Recovery**: Test backup and restore procedures

### Ongoing Maintenance

- [ ] **Security Updates**: Regular OS and dependency updates
- [ ] **Token Rotation**: Periodic API token rotation
- [ ] **Capacity Planning**: Monitor growth and scale accordingly
- [ ] **Performance Tuning**: Optimize based on usage patterns
- [ ] **Compliance Audits**: Regular security and compliance reviews

---

**🚀 Ready to deploy?** Choose your deployment strategy and follow the relevant section above!

**🆘 Need help?** Check our [troubleshooting guide](docs/) or [create an issue](https://github.com/your-org/shortlist/issues).