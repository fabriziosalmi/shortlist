# Security Policy

## Supported Versions

The following versions of Shortlist are currently receiving security updates:

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < Latest| :x:                |

We recommend always using the latest version of Shortlist for the best security and features.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### Private Reporting Process

To report a security vulnerability:

1. **Email**: Send details to the repository maintainer
   - Find maintainer contact in the repository settings
   - Use subject line: "Security Vulnerability in Shortlist"

2. **GitHub Security Advisories** (Preferred):
   - Navigate to the [Security tab](https://github.com/fabriziosalmi/shortlist/security)
   - Click "Report a vulnerability"
   - Fill out the security advisory form
   - This allows for private disclosure and coordination

### What to Include

When reporting a vulnerability, please include:

- **Type of vulnerability**: (e.g., authentication bypass, code injection, etc.)
- **Full path to source file(s)**: Related to the manifestation of the issue
- **Location**: Tag or commit of affected code
- **Configuration required**: Any special configuration needed to reproduce
- **Step-by-step instructions**: To reproduce the issue
- **Proof-of-concept**: Or exploit code if available
- **Impact**: What an attacker could achieve
- **Suggested fix**: If you have ideas for remediation

### Response Timeline

- **Initial response**: Within 48 hours
- **Status update**: Within 7 days
- **Resolution timeline**: Depends on severity and complexity

### Disclosure Policy

- **Coordinated disclosure**: We follow responsible disclosure practices
- **Fix timeline**: We aim to address critical issues within 30 days
- **Public disclosure**: After a fix is available and deployed
- **Credit**: Security researchers will be credited (if desired)

## Security Best Practices for Deployment

### Environment Variables

Never commit sensitive data to the repository:

```bash
# BAD - Never do this
export GIT_AUTH_TOKEN="ghp_1234567890abcdef"

# GOOD - Use secure secret management
export GIT_AUTH_TOKEN="$(cat /secure/path/to/token)"
```

### Authentication Tokens

1. **Rotate regularly**: Change API tokens every 90 days
2. **Minimal permissions**: Grant only required scopes
3. **Secure storage**: Use secret management systems
   - AWS Secrets Manager
   - HashiCorp Vault
   - Kubernetes Secrets
4. **Monitor usage**: Check for unauthorized access

### Git Authentication

**SSH Keys (Recommended)**:
```bash
# Generate dedicated key for Shortlist
ssh-keygen -t ed25519 -f ~/.ssh/shortlist_deploy -C "shortlist-bot"

# Use SSH agent
ssh-add ~/.ssh/shortlist_deploy

# Configure Git to use this key
git config core.sshCommand "ssh -i ~/.ssh/shortlist_deploy"
```

**Personal Access Tokens**:
- Use fine-grained tokens with minimal scope
- Set expiration dates
- Revoke immediately if compromised

### Network Security

**Production deployments should**:
- Use HTTPS/TLS for all external communication
- Implement firewall rules to restrict access
- Use private networks for inter-node communication
- Enable authentication on all HTTP endpoints

Example firewall rules:
```bash
# Allow only specific IPs to access Governance API
iptables -A INPUT -p tcp --dport 8004 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8004 -j DROP
```

### Docker Security

**Container best practices**:
```dockerfile
# Use specific versions, not 'latest'
FROM python:3.11-slim

# Run as non-root user
RUN useradd -m -u 1000 shortlist
USER shortlist

# Read-only filesystem where possible
# Use Docker secrets for sensitive data
```

### Branch Protection

Enable these GitHub branch protection rules:

1. **Require pull request reviews**: At least 1 approval
2. **Require status checks**: CI must pass
3. **Restrict who can push**: Limit to bot account for auto-merges
4. **Require signed commits**: Verify commit authenticity

### Secrets Management

**What to protect**:
- GitHub Personal Access Tokens (`GIT_AUTH_TOKEN`)
- API authentication tokens (`MAINTAINER_API_TOKEN`, `CONTRIBUTOR_API_TOKEN`)
- Third-party API keys (`TELEGRAM_API_TOKEN`)
- Database credentials (if applicable)

**Use `secrets.json` properly**:
```bash
# Ensure it's in .gitignore (it already is)
grep secrets.json .gitignore

# Set restrictive permissions
chmod 600 secrets.json

# Never commit - use template instead
cp secrets.json.template secrets.json
# Then fill in actual values
```

### Audit Logging

All operations are logged in Git history:

```bash
# Review recent governance changes
git log --all --oneline --graph assignments.json roster.json

# Check who made changes
git log --author="shortlist-bot" --since="7 days ago"

# Audit API access patterns
grep "API" output/*.log | grep -E "POST|PUT|DELETE"
```

### Multi-Region Security

**Geographic compliance**:
- **GDPR** (EU): Enable `region: eu-west` for EU user data
- **Data residency**: Configure `geographic_config.json` appropriately
- **Cross-region**: Use encrypted connections for sync

**Regional access control**:
```json
{
  "regions": {
    "eu-west": {
      "compliance": "GDPR",
      "data_residency": true,
      "allowed_operations": ["read", "write"]
    }
  }
}
```

## Known Security Considerations

### Git as Coordination Backend

**Strength**: All state changes are auditable and versioned

**Considerations**:
- Repository access controls are critical
- Git history is immutable (cannot delete accidentally committed secrets)
- Use BFG Repo-Cleaner or git-filter-repo if secrets are committed

### Autonomous Node Behavior

**Design**: Nodes operate independently without central authority

**Security implications**:
- Compromised node could claim all tasks
- Mitigated by: Git commit atomicity and conflict resolution
- Monitor: Unexpected node behavior in `roster.json`

### Governance API

**Protection layers**:
1. API token authentication (Maintainer/Contributor tiers)
2. GitHub branch protection
3. Pull request workflow for Contributors
4. Audit trail in Git history

**Attack surface**:
- API endpoints exposed on port 8004
- Recommend: Run behind reverse proxy with rate limiting

## Security Checklist for Production

Before deploying to production:

- [ ] All secrets stored securely (not in code)
- [ ] API tokens rotated and unique per environment
- [ ] Branch protection rules enabled
- [ ] SSH keys or PAT configured for Git
- [ ] HTTPS/TLS enabled for external endpoints
- [ ] Firewall rules configured appropriately
- [ ] Docker containers run as non-root
- [ ] Logging and monitoring configured
- [ ] Backup and disaster recovery tested
- [ ] Security advisory notifications enabled

## Security Updates

To receive security notifications:

1. **Watch the repository**: Click "Watch" → "Custom" → "Security alerts"
2. **GitHub notifications**: Enable security alert emails
3. **Check regularly**: Review the Security tab

## Additional Resources

- [GitHub Security Best Practices](https://docs.github.com/en/code-security)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security](https://docs.docker.com/engine/security/)

## Questions?

For security-related questions that are not vulnerabilities:
- Open a GitHub Discussion
- Tag with "security" label

Thank you for helping keep Shortlist secure!
