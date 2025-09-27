FROM python:3.9-slim

# Installa ffmpeg, necessario per pydub
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# La cartella 'output' conterrà i file audio generati
RUN mkdir -p /app/output

EXPOSE 8000

CMD ["python", "-u", "main.py"]
