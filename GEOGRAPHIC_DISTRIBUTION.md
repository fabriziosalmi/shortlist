# 🌍 Geographic Distribution Guide

This guide explains how to use Shortlist's geographic distribution capabilities for multi-region deployments with automatic failover and conflict resolution.

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Regional Coordination](#regional-coordination)
- [Conflict Resolution](#conflict-resolution)
- [Monitoring](#monitoring)
- [Migration Guide](#migration-guide)

## Overview

Shortlist's geographic distribution system enables:

- **Multi-region deployment** with region-aware task assignment
- **Automatic failover** when regions become unavailable
- **Conflict resolution** for cross-region data synchronization
- **Regional compliance** (GDPR, data residency requirements)
- **Edge optimization** with content delivery closer to users

### Key Features

- **Backward Compatible**: Existing single-region deployments continue to work unchanged
- **Gradual Adoption**: Enable features incrementally as needed
- **Flexible Consistency**: Choose between eventual and strong consistency per operation type
- **Smart Conflict Resolution**: Semantic merging for content, priority-based for critical operations

## Quick Start

### 1. Single Region (Default Behavior)

No changes needed - existing deployment continues to work:

```bash
python node.py
```

### 2. Enable Regional Awareness

Add region information to nodes:

```bash
# Specify region explicitly
python node.py --region us-east

# Let the system detect region (based on hostname/environment)
export SHORTLIST_REGION=eu-west
python node.py
```

### 3. Enable Full Geographic Sharding

Create `geographic_config.json` and enable sharding:

```bash
# Copy template and customize
cp geographic_config.json my_geographic_config.json

# Enable geographic sharding
python node.py --enable-geo-sharding --region us-east
```

## Configuration

### Basic Geographic Configuration

Create `geographic_config.json` in your repository root:

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
      "timezone": "America/New_York"
    },
    "eu-west": {
      "name": "Europe West",
      "priority": 2,
      "weight": 1,
      "timezone": "Europe/London"
    }
  }
}
```

### Regional Task Ownership

Define which regions should handle specific tasks:

```json
{
  "regional_ownership": {
    "us-east": [
      "global_announcements",
      "corporate_updates",
      "governance_api"
    ],
    "eu-west": [
      "gdpr_notices",
      "eu_compliance",
      "european_events"
    ]
  }
}
```

### Consistency Policies

Configure how different operations handle consistency:

```json
{
  "consistency_policies": {
    "shortlist_updates": {
      "consistency": "eventual",
      "max_lag_seconds": 30,
      "conflict_resolution": "semantic_merge"
    },
    "schedule_changes": {
      "consistency": "strong",
      "quorum_required": true,
      "timeout_seconds": 10
    }
  }
}
```

## Regional Coordination

### Node Assignment

Nodes automatically discover their region and participate in regional coordination:

```bash
# US East region
python node.py --region us-east

# Europe West region
python node.py --region eu-west

# Asia Pacific region
python node.py --region asia-pacific
```

### Task Distribution

Tasks can specify regional requirements:

```json
{
  "tasks": [
    {
      "id": "eu_compliance_check",
      "type": "api",
      "required_region": "eu-west",
      "priority": 1
    },
    {
      "id": "global_dashboard",
      "type": "dashboard",
      "priority": 2
    }
  ]
}
```

### Cross-Region Sync

The system automatically handles cross-region synchronization:

- **Eventual Consistency**: Content updates sync within 30 seconds
- **Strong Consistency**: Critical operations require quorum
- **Conflict Detection**: Automatic detection and resolution of conflicts

## Conflict Resolution

### Strategies

1. **Last Writer Wins**: Simple timestamp-based resolution
2. **Semantic Merge**: Intelligent merging for shortlist content
3. **Region Priority**: US-East preferred for tie-breaking
4. **Timestamp Priority**: Oldest change wins for stability

### Example: Shortlist Content Conflict

When multiple regions update shortlist.json simultaneously:

```json
// Region US-East
{"items": ["Item A", "Item B"]}

// Region EU-West
{"items": ["Item A", "Item C"]}

// Resolved Result (semantic merge)
{"items": ["Item A", "Item B", "Item C"]}
```

### Monitoring Conflicts

Check conflict resolution logs:

```bash
# View conflict resolution activity
grep "conflict" output/*.log

# Get conflict statistics
curl http://localhost:8005/api/regional-stats
```

## Monitoring

### Regional Statistics

Monitor regional distribution through the Control Room:

- **Node Distribution**: How many nodes per region
- **Task Assignment**: Which region handles what
- **Conflict Rate**: Frequency of cross-region conflicts
- **Sync Latency**: How quickly changes propagate

### Health Metrics

Key metrics to monitor:

- **Cross-region latency**: Should be < 500ms
- **Conflict rate**: Should be < 1%
- **Convergence time**: Should be < 30 seconds
- **Regional availability**: Per-region uptime

### Alerts

Set up alerts for:

- High conflict rates (> 5%)
- Slow cross-region sync (> 60s)
- Regional network partitions
- Coordinator failover events

## Migration Guide

### Phase 1: Enable Regional Awareness

1. **No Configuration Changes**: Just add region info to nodes
   ```bash
   python node.py --region us-east
   ```

2. **Update Deployment Scripts**: Add region parameters
   ```bash
   # Docker deployment
   docker run -e SHORTLIST_REGION=eu-west shortlist-node

   # Kubernetes
   env:
   - name: SHORTLIST_REGION
     value: "eu-west"
   ```

### Phase 2: Configure Regional Policies

1. **Create Configuration**: Copy and customize `geographic_config.json`
2. **Define Ownership**: Specify which regions own which tasks
3. **Set Consistency**: Choose consistency levels per operation

### Phase 3: Enable Full Sharding

1. **Separate Git Repos**: Create per-region repositories
   ```json
   {
     "regions": {
       "us-east": {
         "git_repo": "git@github.com:company/shortlist-us.git"
       },
       "eu-west": {
         "git_repo": "git@github.com:company/shortlist-eu.git"
       }
     }
   }
   ```

2. **Enable Sharding**: Start nodes with geographic sharding
   ```bash
   python node.py --enable-geo-sharding --region us-east
   ```

### Rollback Plan

If issues occur, disable geographic features:

```bash
# Disable geographic sharding
python node.py  # Falls back to single-region mode

# Remove regional configuration
mv geographic_config.json geographic_config.json.backup
```

## Command Line Options

```bash
# Basic usage (backward compatible)
python node.py

# Specify region
python node.py --region eu-west

# Enable geographic sharding
python node.py --enable-geo-sharding

# Combine with existing role system
python node.py --region us-east --roles system,media

# Full geographic deployment
python node.py --enable-geo-sharding --region asia-pacific --roles web,broadcaster
```

## Environment Variables

- `SHORTLIST_REGION`: Override automatic region detection
- `SHORTLIST_GEO_CONFIG`: Path to custom geographic configuration file

## Troubleshooting

### Common Issues

1. **Region Detection Fails**
   ```bash
   # Solution: Explicitly set region
   export SHORTLIST_REGION=us-east
   python node.py
   ```

2. **Cross-Region Conflicts**
   ```bash
   # Check conflict logs
   grep "cross-region conflict" output/*.log

   # Adjust consistency policies in geographic_config.json
   ```

3. **Network Partitions**
   ```bash
   # Monitor regional connectivity
   python -c "from utils.geographic import get_geographic_manager; print(get_geographic_manager().get_regional_statistics())"
   ```

### Debug Mode

Enable detailed geographic logging:

```bash
# In geographic_config.json
{
  "geo_metrics": {
    "monitoring": {
      "enabled": true,
      "debug": true
    }
  }
}
```

## Best Practices

1. **Start Small**: Enable regional awareness before full sharding
2. **Monitor Conflicts**: Keep conflict rate below 1%
3. **Test Failover**: Regularly test cross-region failover
4. **Document Ownership**: Clearly define which region owns what
5. **Plan for Partitions**: Design for network partition scenarios

## Security Considerations

- **Regional Isolation**: Sensitive data can be kept region-specific
- **Compliance**: GDPR data stays in EU, etc.
- **Access Control**: Regional-specific API tokens
- **Audit Trail**: Cross-region operation logging

---

For more information, see the main [README.md](README.md) and [SCALING_ARCHITECTURE.md](SCALING_ARCHITECTURE.md).