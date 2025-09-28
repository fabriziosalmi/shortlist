from flask import Flask, Response
import json

app = Flask(__name__)

SHORTLIST_FILE = '/app/data/shortlist.json'

def read_shortlist(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

@app.route('/')
def index():
    shortlist_data = read_shortlist(SHORTLIST_FILE)
    items = shortlist_data.get('items', [])
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Shortlist</title>
</head>
<body>
    <h1>Shortlist</h1>
    <ul>
"""
    for item in items:
        html += f"        <li>{item}</li>\n"
    html += """    </ul>
</body>
</html>"""
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    print("[WebRenderer] ✅ Avviato.")
    app.run(host='0.0.0.0', port=8000)

