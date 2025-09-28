import json
import os
import logging
from gtts import gTTS
from pydub import AudioSegment

from flask import Flask, send_file, Response

logging.basicConfig(filename='/app/data/audio.log', level=logging.INFO)

# --- Configuration ---
SHORTLIST_FILE = '/app/data/shortlist.json'
OUTPUT_DIR = '/app/output'
GENERATED_MP3_FILE = os.path.join(OUTPUT_DIR, 'shortlist_loop.mp3')

# --- Audio Generation Logic ---
def generate_audio_file():
    logging.info("[AudioRenderer] 🎤 Starting audio file generation...")
    try:
        with open(SHORTLIST_FILE, 'r') as f:
            items = json.load(f).get('items', [])
    except Exception as e:
        logging.error(f"[AudioRenderer] 🚨 Error reading shortlist: {e}")
        return False

    if not items:
        logging.warning("[AudioRenderer] ⚠️ Empty shortlist.")
        return False

    pause = AudioSegment.silent(duration=3000)
    final_audio = pause

    for i, item_text in enumerate(items, 1):
        logging.info(f"    - Synthesizing: '{item_text}'")
        try:
            tts = gTTS(f"Point {i}: {item_text}", lang='en')
            temp_path = f"/tmp/item_{i}.mp3"
            tts.save(temp_path)
            item_audio = AudioSegment.from_mp3(temp_path)
            final_audio += item_audio + pause
        except Exception as e:
            logging.error(f"    - 🚨 Error during synthesis: {e}")

    logging.info(f"    - Exporting final audio file to: {GENERATED_MP3_FILE}")
    final_audio.export(GENERATED_MP3_FILE, format="mp3")
    logging.info("[AudioRenderer] ✅ Audio file generated.")
    return True

# --- Web Server Logic ---
app = Flask(__name__)

@app.route('/')
def index():
    html_content = f"""<!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"UTF-8\">
        <title>Shortlist Audio Stream</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #111; color: #eee; margin: 0; flex-direction: column; }}
            h1 {{ margin-bottom: 20px; }}
            audio {{ width: 80%; max-width: 500px; }}
        </style>
    </head>
    <body>
        <h1>Shortlist Audio Stream</h1>
        <audio controls autoplay loop>
            <source src=\"/stream.mp3\" type=\"audio/mpeg\">
            Your browser does not support the audio element.
        </audio>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/stream.mp3')
def stream_mp3():
    if not os.path.exists(GENERATED_MP3_FILE):
        return "Audio file not yet generated.", 404
    return send_file(GENERATED_MP3_FILE, mimetype='audio/mpeg')

def main():
    logging.info("[AudioRenderer] ✅ Started.")
    # Generate the audio file once at startup
    if generate_audio_file():
        logging.info("[AudioRenderer] 🌍 Starting web server on port 8000...")
        # Listen on all interfaces within the container
        app.run(host='0.0.0.0', port=8000)
    else:
        logging.error("[AudioRenderer] 🛑 Startup failed, unable to generate audio file.")

if __name__ == "__main__":
    main()