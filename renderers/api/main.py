from flask import Flask, jsonify
import json

import logging

logging.basicConfig(filename='/app/data/api.log', level=logging.INFO)

app = Flask(__name__)

SHORTLIST_FILE = '/app/data/shortlist.json'

def read_shortlist(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error("Could not read shortlist.json")
        return {}

@app.route('/api/shortlist')
def api_shortlist():
    logging.info("API request received")
    shortlist_data = read_shortlist(SHORTLIST_FILE)
    return jsonify(shortlist_data)

if __name__ == '__main__':
    logging.info("[ApiRenderer] ✅ Avviato.")
    app.run(host='0.0.0.0', port=8000)
