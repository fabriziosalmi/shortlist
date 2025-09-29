FROM python:3.9-slim

# Install git and clean up in one layer
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Create data and output directories
RUN mkdir -p /app/data /app/output && chown -R 1000:1000 /app/data /app/output

# Expose Prometheus metrics port
EXPOSE 8000

# Run with unbuffered output
CMD ["python", "-u", "main.py"]