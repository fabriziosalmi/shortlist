import json
import os
import logging
import subprocess
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from pydub import AudioSegment
from flask import Flask, send_file, Response

logging.basicConfig(filename='/app/data/video.log', level=logging.INFO)

# --- Configuration ---
SHORTLIST_FILE = '/app/data/shortlist.json'
OUTPUT_DIR = '/app/output'
GENERATED_MP4_FILE = os.path.join(OUTPUT_DIR, 'shortlist_video.mp4')

# --- Video Generation Logic ---
def generate_video_file():
    logging.info("[VideoRenderer] 🎬 Starting video file generation...")
    try:
        with open(SHORTLIST_FILE, 'r') as f:
            items = json.load(f).get('items', [])
    except Exception as e:
        logging.error(f"[VideoRenderer] 🚨 Error reading shortlist: {e}")
        return False

    if not items:
        logging.warning("[VideoRenderer] ⚠️ Empty shortlist.")
        return False

    try:
        # First, generate audio using TTS
        logging.info(f"    - Generating TTS audio...")
        pause = AudioSegment.silent(duration=1000)  # 1 second pause
        final_audio = pause

        for i, item_text in enumerate(items, 1):
            logging.info(f"    - Synthesizing: '{item_text}'")
            try:
                tts = gTTS(item_text, lang='en')
                temp_audio_path = f"/tmp/item_{i}.mp3"
                tts.save(temp_audio_path)
                item_audio = AudioSegment.from_mp3(temp_audio_path)
                final_audio += item_audio + pause
                os.remove(temp_audio_path)  # Clean up immediately
            except Exception as e:
                logging.error(f"    - Error during TTS synthesis: {e}")

        # Export audio to file
        temp_audio_file = os.path.join(OUTPUT_DIR, 'temp_audio.mp3')
        final_audio.export(temp_audio_file, format="mp3")
        audio_duration = len(final_audio) / 1000.0  # Convert to seconds

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

        # Use ffmpeg to create video with audio
        logging.info(f"    - Creating video with audio (duration: {audio_duration:.1f}s)...")
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
            logging.error(f"FFmpeg error: {result.stderr}")
            return False

        # Clean up temp files
        os.remove(temp_image)
        os.remove(temp_audio_file)

        logging.info("[VideoRenderer] ✅ Video file generated.")
        return True

    except Exception as e:
        logging.error(f"[VideoRenderer] 🚨 Error during video generation: {e}")
        return False

# --- Web Server Logic ---
app = Flask(__name__)

@app.route('/')
def index():
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
    if not os.path.exists(GENERATED_MP4_FILE):
        return "Video file not yet generated.", 404
    return send_file(GENERATED_MP4_FILE, mimetype='video/mp4')

def main():
    logging.info("[VideoRenderer] ✅ Started.")
    # Generate the video file once at startup
    if generate_video_file():
        logging.info("[VideoRenderer] 🌍 Starting web server on port 8000...")
        # Listen on all interfaces within the container
        app.run(host='0.0.0.0', port=8000)
    else:
        logging.error("[VideoRenderer] 🛑 Startup failed, unable to generate video file.")

if __name__ == "__main__":
    main()