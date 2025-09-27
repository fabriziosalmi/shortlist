FROM python:3.9-slim

WORKDIR /app

# Qui potrebbero esserci dipendenze per le API, es. 'requests'
# COPY requirements.txt .
# RUN pip install -r requirements.txt

COPY main.py .

CMD ["python", "-u", "main.py"]
