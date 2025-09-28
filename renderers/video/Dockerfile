FROM python:3.9-slim

# Install ffmpeg and fonts
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Create directories for data and output
RUN mkdir -p /app/data /app/output && chown -R 1000:1000 /app/data /app/output

EXPOSE 8000

CMD ["python", "-u", "main.py"]