import json
import os
import subprocess
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from pydub import AudioSegment
from flask import Flask, send_file, Response, request

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('video_renderer', log_level="INFO", log_file='/app/data/video.log')
logger = ComponentLogger('video_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='video')

# --- Configuration ---
SHORTLIST_FILE = '/app/data/shortlist.json'
OUTPUT_DIR = '/app/output'
GENERATED_MP4_FILE = os.path.join(OUTPUT_DIR, 'shortlist_video.mp4')

# --- Video Generation Logic ---
@log_execution_time(logger.logger)
def generate_video_file() -> bool:
    """Generate a video file from the current shortlist content."""
    with log_operation(logger.logger, "generate_video"):
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

    try:
        # First, generate audio using TTS
        logger.logger.info("Generating TTS audio")
        pause = AudioSegment.silent(duration=1000)  # 1 second pause
        final_audio = pause

        for i, item_text in enumerate(items, 1):
            with log_operation(logger.logger, "synthesize_item",
                              item_number=i,
                              text_length=len(item_text)):
                try:
                    tts = gTTS(item_text, lang='en')
                    temp_audio_path = f"/tmp/item_{i}.mp3"
                    tts.save(temp_audio_path)
                    item_audio = AudioSegment.from_mp3(temp_audio_path)
                    final_audio += item_audio + pause
                    os.remove(temp_audio_path)  # Clean up immediately
                except Exception as e:
                    logger.logger.error("Error during TTS synthesis",
                                      error=str(e),
                                      error_type=type(e).__name__)

        # Export audio to file
        temp_audio_file = os.path.join(OUTPUT_DIR, 'temp_audio.mp3')
        final_audio.export(temp_audio_file, format="mp3")
        audio_duration = len(final_audio) / 1000.0  # Convert to seconds
        logger.logger.info("Audio exported",
                          duration_seconds=audio_duration,
                          output=temp_audio_file)

        # Create a simple image with text
        img = Image.new('RGB', (1280, 720), color='black')
        draw = ImageDraw.Draw(img)

        # Try to use a default font
        try:
            font_items = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
        except:
            font_items = ImageFont.load_default()

        # Draw items centered (no title, no bullet points)
        total_height = len(items) * 100  # Estimate total height needed
        start_y = (720 - total_height) // 2  # Center vertically

        y_offset = start_y
        for item in items:
            # Just the content, no bullet points
            text = item
            bbox = draw.textbbox((0, 0), text, font=font_items)
            text_width = bbox[2] - bbox[0]
            draw.text(((1280 - text_width) // 2, y_offset), text, fill='white', font=font_items)
            y_offset += 100

        # Save the image
        temp_image = os.path.join(OUTPUT_DIR, 'temp_frame.png')
        img.save(temp_image)
        logger.logger.info("Image frame saved", path=temp_image)

        # Use ffmpeg to create video with audio
        logger.logger.info("Creating video with audio", duration_seconds=audio_duration)
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', temp_image,
            '-i', temp_audio_file,
            '-t', str(audio_duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-pix_fmt', 'yuv420p',
            '-r', '24',
            '-shortest',  # End when shortest input ends
            GENERATED_MP4_FILE
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.logger.error("FFmpeg error", stderr=result.stderr)
            return False

        # Clean up temp files
        os.remove(temp_image)
        os.remove(temp_audio_file)

        logger.logger.info("Video file generated", output=GENERATED_MP4_FILE)
        return True

    except Exception as e:
        logger.logger.error("Error during video generation",
                          error=str(e),
                          error_type=type(e).__name__)
        return False

# --- Web Server Logic ---
app = Flask(__name__)

@app.route('/')
def index():
    with log_operation(logger.logger, "serve_index",
                      path=request.path,
                      remote_addr=request.remote_addr):
        html_content = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Shortlist Video Stream</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #111; color: #eee; margin: 0; flex-direction: column; }}
            h1 {{ margin-bottom: 20px; }}
            video {{ width: 80%; max-width: 800px; }}
        </style>
    </head>
    <body>
        <h1>Shortlist Video Stream</h1>
        <video controls autoplay loop>
            <source src="/stream.mp4" type="video/mp4">
            Your browser does not support the video element.
        </video>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/stream.mp4')
def stream_mp4():
    with log_operation(logger.logger, "stream_video",
                      path=request.path,
                      remote_addr=request.remote_addr):
        if not os.path.exists(GENERATED_MP4_FILE):
            logger.logger.warning("Video file not found",
                               filepath=GENERATED_MP4_FILE)
            return "Video file not yet generated.", 404
        return send_file(GENERATED_MP4_FILE, mimetype='video/mp4')

def main():
    logger.log_startup()
    # Generate the video file once at startup
    if generate_video_file():
        logger.logger.info("Starting web server", host='0.0.0.0', port=8000)
        # Listen on all interfaces within the container
        app.run(host='0.0.0.0', port=8000)
        logger.log_shutdown()
    else:
        logger.logger.error("Startup failed", reason="Unable to generate video file")
        logger.log_shutdown(status='error')

if __name__ == "__main__":
    main()