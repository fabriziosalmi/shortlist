import json
import os
from gtts import gTTS
from pydub import AudioSegment
from typing import List, Dict, Any, Optional

from flask import Flask, send_file, Response, request

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('audio_renderer', log_level="INFO", log_file='/app/data/audio.log')
logger = ComponentLogger('audio_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='audio')

# --- Configuration ---
SHORTLIST_FILE = '/app/data/shortlist.json'
OUTPUT_DIR = '/app/output'
GENERATED_MP3_FILE = os.path.join(OUTPUT_DIR, 'shortlist_loop.mp3')

# --- Audio Generation Logic ---
@log_execution_time(logger.logger)
def generate_audio_file() -> bool:
    """Generate an audio file from the current shortlist content.
    
    Returns:
        bool: True if generation was successful, False otherwise
    """
    with log_operation(logger.logger, "generate_audio"):
        try:
            with open(SHORTLIST_FILE, 'r') as f:
                items = json.load(f).get('items', [])
        except Exception as e:
            logger.logger.error("Failed to read shortlist",
                              error=str(e),
                              error_type=type(e).__name__,
                              filepath=SHORTLIST_FILE)
            return False

        if not items:
            logger.logger.warning("Empty shortlist")
            return False

        logger.logger.info("Starting audio generation", items_count=len(items))
        
        pause = AudioSegment.silent(duration=3000)
        final_audio = pause

        for i, item_text in enumerate(items, 1):
            with log_operation(logger.logger, "synthesize_item",
                              item_number=i,
                              text_length=len(item_text)):
                try:
                    tts = gTTS(f"Point {i}: {item_text}", lang='en')
                    temp_path = f"/tmp/item_{i}.mp3"
                    tts.save(temp_path)
                    item_audio = AudioSegment.from_mp3(temp_path)
                    final_audio += item_audio + pause
                    logger.logger.info("Item synthesized successfully",
                                      item_number=i)
                except Exception as e:
                    logger.logger.error("Failed to synthesize item",
                                      error=str(e),
                                      error_type=type(e).__name__,
                                      item_number=i)

        logger.logger.info("Exporting final audio",
                          output_path=GENERATED_MP3_FILE)
        final_audio.export(GENERATED_MP3_FILE, format="mp3")
        logger.logger.info("Audio generation completed")
        return True

# --- Web Server Logic ---
app = Flask(__name__)

@app.route('/')
def index():
    """Serve the main HTML interface with audio player."""
    with log_operation(logger.logger, "serve_index",
                      path=request.path,
                      remote_addr=request.remote_addr):
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
    """Stream the generated MP3 file."""
    with log_operation(logger.logger, "stream_audio",
                      path=request.path,
                      remote_addr=request.remote_addr):
        if not os.path.exists(GENERATED_MP3_FILE):
            logger.logger.warning("Audio file not found",
                               filepath=GENERATED_MP3_FILE)
            return "Audio file not yet generated.", 404
            
        logger.logger.info("Streaming audio file")
        return send_file(GENERATED_MP3_FILE, mimetype='audio/mpeg')

def main() -> None:
    """Main entry point for the audio renderer."""
    logger.log_startup()
    
    # Generate the audio file once at startup
    if generate_audio_file():
        logger.logger.info("Starting web server",
                         host="0.0.0.0",
                         port=8000)
        # Listen on all interfaces within the container
        app.run(host='0.0.0.0', port=8000)
        logger.log_shutdown()
    else:
        logger.logger.error("Startup failed",
                          reason="Unable to generate audio file")
        logger.log_shutdown(status="error")

if __name__ == "__main__":
    main()