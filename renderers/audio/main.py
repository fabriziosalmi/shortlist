import json
import os
import importlib.util
from pathlib import Path
from gtts import gTTS
from pydub import AudioSegment
from typing import List, Dict, Any, Optional

from utils.template_processor import process_shortlist_content

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
TASK_CONFIG_FILE = '/app/config/task_config.json'

class AudioRenderer:
    def __init__(self, logger: ComponentLogger):
        self.logger = logger
        self.plugins = []
        
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

# --- Audio Generation Logic ---
@log_execution_time(logger.logger)
def generate_audio_file(renderer) -> bool:
    """Generate an audio file from the current shortlist content.
    
    Args:
        renderer: AudioRenderer instance with plugins
    
    Returns:
        bool: True if generation was successful, False otherwise
    """
    with log_operation(logger.logger, "generate_audio"):
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

        logger.logger.info("Starting audio generation",
                        items_count=len(items),
                        plugins_count=len(renderer.plugins))
        
        # Generate transition audio (pause or custom from plugins)
        def get_transition(prev_item, next_item):
            transition = AudioSegment.silent(duration=3000)
            for plugin in renderer.plugins:
                plugin_transition = plugin.insert_between_segments(prev_item, next_item)
                if plugin_transition is not None:
                    transition = transition.overlay(plugin_transition)
            return transition
        
        # Start with initial transition
        final_audio = get_transition(None, 1)

        for i, item_text in enumerate(items, 1):
            with log_operation(logger.logger, "synthesize_item",
                              item_number=i,
                              text_length=len(item_text)):
                try:
                    # Extract content from item if it's a dict, or use directly if it's a string
                    content = item_text.get('content', item_text) if isinstance(item_text, dict) else item_text
                    
                    # Generate TTS audio
                    tts = gTTS(f"Point {i}: {content}", lang='en')
                    temp_path = f"/tmp/item_{i}.mp3"
                    tts.save(temp_path)
                    item_audio = AudioSegment.from_mp3(temp_path)
                    
                    # Apply plugin processing
                    for plugin in renderer.plugins:
                        item_audio = plugin.process_audio_segment(item_audio, i)
                    
                    # Add audio and transition to next item
                    final_audio += item_audio
                    next_item = i + 1 if i < len(items) else None
                    final_audio += get_transition(i, next_item)
                    
                    logger.logger.info("Item synthesized successfully",
                                      item_number=i)
                    
                    # Clean up temp file
                    os.unlink(temp_path)
                    
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
    
    # Initialize renderer and plugins
    renderer = AudioRenderer(logger)
    if not renderer.load_plugins():
        logger.logger.error("Startup failed",
                         reason="Failed to load plugins")
        logger.log_shutdown(status="error")
        return
    
    # Generate the audio file once at startup
    if generate_audio_file(renderer):
        logger.logger.info("Starting web server",
                         host="0.0.0.0",
                         port=8000)
        # Listen on all interfaces within the container
        app.run(host='0.0.0.0', port=8000)
        renderer.cleanup_plugins()
        logger.log_shutdown()
    else:
        logger.logger.error("Startup failed",
                          reason="Unable to generate audio file")
        renderer.cleanup_plugins()
        logger.log_shutdown(status="error")

if __name__ == "__main__":
    main()