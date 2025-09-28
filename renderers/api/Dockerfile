FROM python:3.11-slim

# Install git and other necessary tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create entrypoint script
RUN cat > /app/entrypoint.sh << 'EOF'
#!/bin/bash
set -e

# Configure Git for the bot user
git config --global user.email "bot@shortlist.io"
git config --global user.name "Shortlist Bot"

# Verify required environment variables
if [ -z "$MAINTAINER_API_TOKEN" ]; then
    echo "WARNING: MAINTAINER_API_TOKEN not set - admin endpoints will be disabled"
fi

if [ -z "$CONTRIBUTOR_API_TOKEN" ]; then
    echo "WARNING: CONTRIBUTOR_API_TOKEN not set - contributor endpoints will be disabled"
fi

if [ -z "$GIT_AUTH_TOKEN" ]; then
    echo "ERROR: GIT_AUTH_TOKEN is required for GitHub operations"
    exit 1
fi

if [ -z "$GITHUB_REPO" ]; then
    echo "ERROR: GITHUB_REPO is required (format: owner/repo)"
    exit 1
fi

echo "Starting Shortlist Governance API..."
echo "GitHub Repository: $GITHUB_REPO"
echo "Maintainer Auth: $([ -n "$MAINTAINER_API_TOKEN" ] && echo "✓ Configured" || echo "✗ Not configured")"
echo "Contributor Auth: $([ -n "$CONTRIBUTOR_API_TOKEN" ] && echo "✓ Configured" || echo "✗ Not configured")"

# Start the FastAPI application
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
EOF

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Create directories and set permissions
RUN mkdir -p /app/data && chown -R 1000:1000 /app

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]