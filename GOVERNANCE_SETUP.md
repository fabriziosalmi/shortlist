# Shortlist Governance API Setup Guide

This guide explains how to configure the **Shortlist Governance API** with "Trust Circles" architecture for secure, tiered access control.

## Overview

The Governance API provides two levels of access:

- **🔑 Maintainer Level**: Can update the shortlist directly (auto-merged PRs)
- **👥 Contributor Level**: Can propose changes (PRs requiring review)

## Prerequisites

- GitHub repository with Shortlist system
- GitHub account for the bot
- Docker and Docker Compose (optional)

## Setup Steps

### 1. Create GitHub Bot Account

Create a dedicated GitHub account for the bot (e.g., `shortlist-bot`):

1. Create new GitHub account: `shortlist-bot`
2. Add this account as a **collaborator** to your Shortlist repository
3. Grant **Write** permissions to the bot account

### 2. Generate GitHub Personal Access Token (PAT)

1. Log in as the bot account (`shortlist-bot`)
2. Go to **Settings → Developer settings → Personal access tokens → Tokens (classic)**
3. Click **Generate new token (classic)**
4. Configure the token:
   - **Note**: `Shortlist Governance API`
   - **Expiration**: Choose appropriate duration
   - **Scopes**: Select the following:
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)
     - ✅ `write:discussion` (Write access to discussions)

5. **Copy the generated token** - you'll need it as `GIT_AUTH_TOKEN`

### 3. Configure Branch Protection (Recommended)

To enforce the governance model properly:

1. Go to your repository **Settings → Branches**
2. Add rule for `main` branch:
   - ✅ **Require a pull request before merging**
   - ✅ **Require approvals**: 1
   - ✅ **Dismiss stale PR approvals when new commits are pushed**
   - ✅ **Allow specified actors to bypass required pull requests**: Add `shortlist-bot`

### 4. Generate API Tokens

Generate two UUID tokens for API access:

```bash
# Generate Maintainer token
python3 -c "import uuid; print('MAINTAINER_API_TOKEN=' + str(uuid.uuid4()))"

# Generate Contributor token
python3 -c "import uuid; print('CONTRIBUTOR_API_TOKEN=' + str(uuid.uuid4()))"
```

Save these tokens securely - they will be used to authenticate API requests.

### 5. Environment Variables

The API renderer requires these environment variables:

```bash
# Required for GitHub operations
export GIT_AUTH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"  # Bot's GitHub PAT
export GITHUB_REPO="your-username/your-repo"      # Format: owner/repo

# API Authentication tokens (UUIDs you generated)
export MAINTAINER_API_TOKEN="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export CONTRIBUTOR_API_TOKEN="yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
```

### 6. Update Schedule Configuration

Add the API task to your `schedule.json`:

```json
{
  "tasks": [
    { "id": "telegram_text_posts", "type": "text", "priority": 0 },
    { "id": "shortlist_video", "type": "video", "priority": 1 },
    { "id": "shortlist_governance_api", "type": "api", "priority": 2 }
  ]
}
```

### 7. Run the System

Start a node with the environment variables:

```bash
# Set all environment variables first
export GIT_AUTH_TOKEN="your_github_pat"
export GITHUB_REPO="owner/repo"
export MAINTAINER_API_TOKEN="your_maintainer_uuid"
export CONTRIBUTOR_API_TOKEN="your_contributor_uuid"

# Start the node
python3 node.py
```

The API will be available at: **http://localhost:8004**

## API Usage

### Maintainer Endpoints (Auto-merge)

**Update Shortlist (Immediate merge):**

```bash
curl -X POST http://localhost:8004/v1/admin/shortlist \
  -H "Authorization: Bearer YOUR_MAINTAINER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["FreeTekno", "New Item", "Another Item"]
  }'
```

### Contributor Endpoints (Proposal)

**Propose Shortlist Changes:**

```bash
curl -X POST http://localhost:8004/v1/proposals/shortlist \
  -H "Authorization: Bearer YOUR_CONTRIBUTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": ["FreeTekno", "Proposed Item"],
    "description": "Adding new trending topic"
  }'
```

### Status Endpoint

**Check API Configuration:**

```bash
curl http://localhost:8004/v1/status
```

### Health Check

```bash
curl http://localhost:8004/health
```

## API Documentation

Once running, view the interactive API documentation at:

- **Swagger UI**: http://localhost:8004/docs
- **ReDoc**: http://localhost:8004/redoc

## Security Considerations

1. **Token Security**: Store API tokens securely and rotate them regularly
2. **Network Security**: Consider running the API behind a reverse proxy with HTTPS
3. **Rate Limiting**: Implement rate limiting for production use
4. **Audit Logging**: All changes are tracked via GitHub's built-in audit trail
5. **Branch Protection**: Ensure branch protection rules are properly configured

## Troubleshooting

### Common Issues

**1. "GIT_AUTH_TOKEN is required" error:**
- Ensure the GitHub PAT is properly set and has correct permissions

**2. "Failed to clone repository" error:**
- Check that the bot account has access to the repository
- Verify the `GITHUB_REPO` format is correct (`owner/repo`)

**3. "Failed to create pull request" error:**
- Ensure the bot has write permissions to the repository
- Check that branch protection rules allow the bot to create PRs

**4. Container startup failures:**
- Check Docker logs: `docker logs <container_name>`
- Verify all required environment variables are set

### Debug Mode

To enable debug logging, add to the container environment:

```bash
export LOG_LEVEL="DEBUG"
```

## Integration Examples

### GitHub Actions Integration

You can trigger the API from GitHub Actions:

```yaml
- name: Update Shortlist
  run: |
    curl -X POST ${{ secrets.SHORTLIST_API_URL }}/v1/admin/shortlist \
      -H "Authorization: Bearer ${{ secrets.MAINTAINER_API_TOKEN }}" \
      -H "Content-Type: application/json" \
      -d '{"items": ["Item1", "Item2"]}'
```

### External System Integration

The API can be integrated with:
- **Content Management Systems**
- **Social Media Monitoring Tools**
- **Analytics Dashboards**
- **Automated Content Curation Systems**

## Next Steps

After setup, consider implementing:

1. **Rate limiting** using nginx or API gateway
2. **Monitoring** with Prometheus/Grafana
3. **Backup strategies** for critical data
4. **Disaster recovery** procedures
5. **Additional authentication** methods (OAuth, JWT)

For questions or issues, check the main repository documentation or create an issue.