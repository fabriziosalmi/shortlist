FROM python:3.9-slim

# Install git
RUN apt-get update && apt-get install -y git

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "/app/workers/watcher_worker/main.py"]
