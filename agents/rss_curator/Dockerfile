FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent files
COPY curator.py .
COPY config.json .

# Create volume mount point for state
VOLUME /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV STATE_DB_PATH=/app/data/state.db

# Run curator
CMD ["python", "curator.py"]