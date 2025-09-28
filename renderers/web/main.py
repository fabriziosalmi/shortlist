from flask import Flask, Response
import json
import logging

logging.basicConfig(filename='/app/data/web.log', level=logging.INFO)

app = Flask(__name__)

SHORTLIST_FILE = '/app/data/shortlist.json'

def read_shortlist(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("Could not read shortlist.json")
        return {}

@app.route('/')
def index():
    logging.info("Web request received")
    shortlist_data = read_shortlist(SHORTLIST_FILE)
    items = shortlist_data.get('items', [])
    html = f"<h1>Shortlist</h1><ul>{''.join([f'<li>{item}</li>' for item in items])}</ul>"
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    logging.info("[WebRenderer] ✅ Avviato.")
    app.run(host='0.0.0.0', port=8000)

