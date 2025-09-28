FROM python:3.11-slim

# Install git and other necessary tools
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Configure Git for the bot user
RUN git config --global user.email "governor@shortlist.io"
RUN git config --global user.name "Shortlist Governor"

# Create data directory for mounting volumes
RUN mkdir -p /app/data

# Run the governor
CMD ["python", "main.py"]