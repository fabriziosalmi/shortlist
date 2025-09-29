import json
import os
import importlib.util
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip

from utils.template_processor import process_shortlist_content
from flask import Flask, send_file, Response, request

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

from plugins.base import RenderContext

# Configure logging
configure_logging('video_renderer', log_level="INFO", log_file='/app/data/video.log')
logger = ComponentLogger('video_renderer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='video')

# --- Configuration ---
SHORTLIST_FILE = '/app/data/shortlist.json'
OUTPUT_DIR = '/app/output'
GENERATED_MP4_FILE = os.path.join(OUTPUT_DIR, 'shortlist_video.mp4')
TASK_CONFIG_FILE = '/app/config/task_config.json'

class VideoRenderer:
    def __init__(self, logger: ComponentLogger):
        self.logger = logger
        self.plugins = []
        self.context = RenderContext()
        
    def load_plugins(self) -> bool:
        """Load and initialize plugins from configuration."""
        try:
            # Read plugin configuration
            if not os.path.exists(TASK_CONFIG_FILE):
                self.logger.info("No task configuration file found, skipping plugins")
                return True
                
            with open(TASK_CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            plugins_config = config.get('plugins', [])
            if not plugins_config:
                self.logger.info("No plugins configured")
                return True
            
            # Load each enabled plugin
            for plugin_config in plugins_config:
                if not plugin_config.get('enabled', False):
                    continue
                    
                name = plugin_config.get('name')
                if not name:
                    self.logger.warning("Plugin config missing name, skipping",
                                     config=plugin_config)
                    continue
                
                try:
                    # Import the plugin module
                    plugin_path = Path(__file__).parent / 'plugins' / f"{name}.py"
                    spec = importlib.util.spec_from_file_location(name, plugin_path)
                    if not spec or not spec.loader:
                        raise ImportError(f"Could not load plugin spec: {name}")
                        
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Initialize the plugin
                    plugin = module.Plugin(plugin_config.get('settings', {}), self.logger)
                    
                    # Run startup hook
                    if not plugin.on_startup():
                        self.logger.error("Plugin startup failed", plugin=name)
                        continue
                    
                    self.plugins.append(plugin)
                    self.logger.info("Plugin loaded successfully", plugin=name)
                    
                except Exception as e:
                    self.logger.error("Failed to load plugin",
                                  plugin=name,
                                  error=str(e),
                                  error_type=type(e).__name__)
                    continue
                    
            return True
            
        except Exception as e:
            self.logger.error("Failed to load plugins",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def cleanup_plugins(self) -> None:
        """Call shutdown hook on all plugins."""
        for plugin in self.plugins:
            try:
                plugin.on_shutdown()
            except Exception as e:
                self.logger.error("Plugin shutdown failed",
                              error=str(e),
                              error_type=type(e).__name__)
                              
    def create_frame(self, text: str, item_number: int) -> Image.Image:
        """Create a video frame with text."""
        img = Image.new('RGB', (self.context.video_width, self.context.video_height), 
                       color=self.context.background_color)
        
        # If we have a background image, use it
        if self.context.background_image and os.path.exists(self.context.background_image):
            bg = Image.open(self.context.background_image)
            # Resize to fit, maintaining aspect ratio
            bg.thumbnail((self.context.video_width, self.context.video_height))
            # Center the background
            x = (self.context.video_width - bg.width) // 2
            y = (self.context.video_height - bg.height) // 2
            img.paste(bg, (x, y))
        
        draw = ImageDraw.Draw(img)
        font = self.context.get_font()
        
        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.context.video_width - text_width) // 2
        y = (self.context.video_height - font.size) // 2
        
        draw.text((x, y), text, fill=self.context.font_color, font=font)
        
        # Apply frame processing plugins
        for plugin in self.plugins:
            img = plugin.process_frame(img, item_number)
        
        return img

# --- Video Generation Logic ---
@log_execution_time(logger.logger)
def generate_video_file(renderer) -> bool:
    """Generate a video file from the current shortlist content.
    
    Args:
        renderer: VideoRenderer instance with plugins
    """
    with log_operation(logger.logger, "generate_video"):
        try:
            # Read and process the shortlist with templates
            with open(SHORTLIST_FILE, 'r') as f:
                shortlist_data = json.load(f)
            
            processed_data = process_shortlist_content(shortlist_data)
            items = processed_data.get('items', [])
        except Exception as e:
            logger.logger.error("Failed to read or process shortlist",
                              error=str(e),
                              error_type=type(e).__name__,
                              filepath=SHORTLIST_FILE)
            return False

    if not items:
        logger.logger.warning("Empty shortlist")
        return False

    try:
        # Let plugins modify the render context
        for plugin in renderer.plugins:
            renderer.context = plugin.on_before_render(renderer.context)

        # First, generate audio using TTS
        logger.logger.info("Generating TTS audio")
        pause = AudioSegment.silent(duration=1000)  # 1 second pause
        final_audio = pause

        # Create frames and clips for all items
        clips = []
        frames = []
        
        for i, item_text in enumerate(items, 1):
            with log_operation(logger.logger, "synthesize_item",
                              item_number=i,
                              text_length=len(item_text)):
                try:
                    # Extract content from item if it's a dict, or use directly if it's a string
                    content = item_text.get('content', item_text) if isinstance(item_text, dict) else item_text
                    
                    # Generate audio
                    tts = gTTS(content, lang='en')
                    temp_audio_path = f"/tmp/item_{i}.mp3"
                    tts.save(temp_audio_path)
                    item_audio = AudioSegment.from_mp3(temp_audio_path)
                    final_audio += item_audio + pause
                    os.remove(temp_audio_path)  # Clean up immediately
                    
                    # Generate frame with text
                    frame = renderer.create_frame(content, i)
                    frames.append(frame)
                    
                    # Save frame to temp file
                    temp_frame_path = f"/tmp/frame_{i}.png"
                    frame.save(temp_frame_path)
                    
                    # Create clip from frame
                    duration = len(item_audio) / 1000.0  # Convert ms to seconds
                    clip = ImageClip(temp_frame_path).set_duration(duration)
                    clips.append(clip)
                    
                    # If there's a previous frame, check for transitions
                    if i > 1:
                        for plugin in renderer.plugins:
                            transition = plugin.create_transition(
                                frames[-2], frames[-1], duration=0.5)
                            if transition:
                                clips.insert(-1, transition)
                    
                    os.remove(temp_frame_path)  # Clean up
                    
                except Exception as e:
                    logger.logger.error("Error processing item",
                                      error=str(e),
                                      error_type=type(e).__name__,
                                      item_number=i)

        # Export audio to file
        temp_audio_file = os.path.join(OUTPUT_DIR, 'temp_audio.mp3')
        final_audio.export(temp_audio_file, format="mp3")
        logger.logger.info("Audio exported", output=temp_audio_file)
        
        # Concatenate all clips
        logger.logger.info("Assembling video clips")
        video = CompositeVideoClip(clips)
        
        # Let plugins add final effects
        for plugin in renderer.plugins:
            video = plugin.finalize_video(video)
        
        # Add audio
        audio = VideoFileClip(temp_audio_file)
        video = video.set_audio(audio)
        
        # Write final video
        logger.logger.info("Writing video file", output=GENERATED_MP4_FILE)
        video.write_videofile(
            GENERATED_MP4_FILE,
            codec='libx264',
            audio_codec='aac',
            fps=renderer.context.fps
        )
        
        # Clean up temp files
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
    
    # Initialize renderer and plugins
    renderer = VideoRenderer(logger)
    if not renderer.load_plugins():
        logger.logger.error("Startup failed", reason="Failed to load plugins")
        logger.log_shutdown(status="error")
        return
    
    # Generate the video file once at startup
    if generate_video_file(renderer):
        logger.logger.info("Starting web server", host='0.0.0.0', port=8000)
        # Listen on all interfaces within the container
        app.run(host='0.0.0.0', port=8000)
        renderer.cleanup_plugins()
        logger.log_shutdown()
    else:
        logger.logger.error("Startup failed", reason="Unable to generate video file")
        renderer.cleanup_plugins()
        logger.log_shutdown(status='error')

if __name__ == "__main__":
    main()