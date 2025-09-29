#!/usr/bin/env python3
"""
Live Streaming Renderer for Shortlist.

This renderer maintains a continuous RTMP stream to platforms like YouTube Live
or Twitch, dynamically updating content based on shortlist.json changes.
"""

import os
import json
import time
import signal
import subprocess
import threading
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import moviepy.editor as mpy
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.VideoClip import ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

from utils.logging_config import configure_logging
from utils.logging_utils import (
    ComponentLogger,
    RENDERER_CONTEXT,
    log_operation,
    log_execution_time
)

# Configure logging
configure_logging('live_streamer', log_level="INFO", log_file='/app/data/live_stream.log')
logger = ComponentLogger('live_streamer')
logger.logger.add_context(**RENDERER_CONTEXT, renderer_type='live_streamer')

class StreamConfig:
    """Configuration for the live stream."""
    
    def __init__(self, config_file: str = '/app/config/task_config.json'):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        self.rtmp_url = config['rtmp_url']
        self.stream_key = os.environ.get(config['stream_key_secret_name'])
        if not self.stream_key:
            raise ValueError(f"Missing required stream key: {config['stream_key_secret_name']}")
        
        self.video = config.get('video', {})
        self.resolution = self.video.get('resolution', '1280x720')
        self.framerate = self.video.get('framerate', 24)
        self.video_bitrate = self.video.get('bitrate', '2500k')
        
        self.audio = config.get('audio', {})
        self.audio_bitrate = self.audio.get('bitrate', '128k')
        
        # Work directories
        self.temp_dir = Path('/app/tmp')
        self.temp_dir.mkdir(exist_ok=True)
        self.playlist_file = self.temp_dir / 'playlist.txt'
        self.content_dir = self.temp_dir / 'content'
        self.content_dir.mkdir(exist_ok=True)

class ContentGenerator:
    """Generates video content from shortlist items."""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.width, self.height = map(int, config.resolution.split('x'))
        
        # Load font
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        self.font_size = int(self.height / 15)  # Proportional to height
        self.font = ImageFont.truetype(font_path, self.font_size)
    
    def create_text_clip(self, text: str, duration: int = 10) -> str:
        """Create a video clip from text."""
        # Create background
        color_clip = ColorClip(
            size=(self.width, self.height),
            color=(0, 0, 0),
            duration=duration
        )
        
        # Create text image
        txt_clip = mpy.TextClip(
            text,
            font=self.font.path,
            fontsize=self.font_size,
            color='white',
            size=(self.width * 0.8, None),  # 80% of width, auto height
            method='caption'
        )
        
        # Center the text
        txt_clip = txt_clip.set_position('center')
        
        # Composite
        final_clip = CompositeVideoClip([color_clip, txt_clip])
        
        # Save to temporary file
        output_path = self.config.content_dir / f"text_{hash(text)}_{int(time.time())}.mp4"
        final_clip.write_videofile(
            str(output_path),
            fps=self.config.framerate,
            codec='libx264',
            audio=False
        )
        
        return str(output_path)
    
    def process_item(self, item: Dict[str, Any]) -> Optional[str]:
        """Process a shortlist item and return a path to its media file."""
        try:
            if isinstance(item, str):
                # Legacy string format
                return self.create_text_clip(item)
            
            content_type = item.get('type', 'text')
            content = item.get('content', '')
            
            if content_type == 'text':
                return self.create_text_clip(content)
            elif content_type in ('image', 'video'):
                # For now, just create a text clip
                # TODO: Implement proper image/video handling
                return self.create_text_clip(f"{content_type}: {content}")
            else:
                logger.warning(f"Unsupported content type: {content_type}")
                return None
                
        except Exception as e:
            logger.error("Failed to process item",
                        error=str(e),
                        item=item)
            return None

class FFmpegManager:
    """Manages the FFmpeg streaming process."""
    
    def __init__(self, config: StreamConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.should_run = True
        signal.signal(signal.SIGTERM, self.handle_signal)
    
    def handle_signal(self, signum, frame):
        """Handle termination signals gracefully."""
        logger.info("Received shutdown signal")
        self.should_run = False
        self.stop_stream()
    
    def build_command(self) -> List[str]:
        """Build the FFmpeg command for streaming."""
        return [
            'ffmpeg',
            '-re',                    # Read input at native framerate
            '-f', 'concat',           # Use concat demuxer
            '-safe', '0',             # Allow unsafe file paths
            '-i', str(self.config.playlist_file),
            
            # Video settings
            '-c:v', 'libx264',        # H.264 codec
            '-preset', 'veryfast',    # Encoding preset
            '-b:v', self.config.video_bitrate,
            '-maxrate', self.config.video_bitrate,
            '-bufsize', str(int(self.config.video_bitrate.replace('k', '')) * 2) + 'k',
            '-g', str(self.config.framerate * 2),  # GOP size
            '-keyint_min', str(self.config.framerate),
            '-r', str(self.config.framerate),
            
            # Audio settings
            '-c:a', 'aac',
            '-b:a', self.config.audio_bitrate,
            
            # Output settings
            '-f', 'flv',              # FLV format for RTMP
            f"{self.config.rtmp_url}/{self.config.stream_key}"
        ]
    
    def start_stream(self) -> None:
        """Start the FFmpeg streaming process."""
        if self.process:
            self.stop_stream()
        
        command = self.build_command()
        logger.info("Starting FFmpeg stream",
                   command=' '.join(command))
        
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            logger.info("FFmpeg stream started")
            
        except Exception as e:
            logger.error("Failed to start FFmpeg",
                        error=str(e))
    
    def stop_stream(self) -> None:
        """Stop the FFmpeg streaming process."""
        if self.process:
            logger.info("Stopping FFmpeg stream")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
    
    def monitor_stream(self) -> None:
        """Monitor the FFmpeg process and restart if needed."""
        while self.should_run:
            if not self.process or self.process.poll() is not None:
                if self.process:
                    # Process died, log error
                    stderr = self.process.stderr.read() if self.process.stderr else "No error output"
                    logger.error("FFmpeg stream died",
                               return_code=self.process.returncode,
                               error_output=stderr)
                
                # Restart the stream
                time.sleep(5)  # Wait before restart
                self.start_stream()
            
            time.sleep(1)

class ContentManager(threading.Thread):
    """Manages content generation and playlist updates."""
    
    def __init__(self, config: StreamConfig):
        super().__init__()
        self.config = config
        self.generator = ContentGenerator(config)
        self.should_run = True
        self.daemon = True
    
    def update_playlist(self, items: List[Dict[str, Any]]) -> None:
        """Update the playlist with new content."""
        # Process all items
        media_files = []
        for item in items:
            file_path = self.generator.process_item(item)
            if file_path:
                media_files.append(file_path)
        
        if not media_files:
            logger.warning("No valid content to stream")
            return
        
        # Create new playlist file
        temp_playlist = self.config.playlist_file.with_suffix('.tmp')
        with open(temp_playlist, 'w') as f:
            for media_file in media_files:
                f.write(f"file '{media_file}'\n")
        
        # Atomic replace
        temp_playlist.replace(self.config.playlist_file)
        logger.info("Updated playlist",
                   items_count=len(media_files))
    
    def read_shortlist(self) -> List[Dict[str, Any]]:
        """Read and parse shortlist.json."""
        try:
            with open('/app/data/shortlist.json', 'r') as f:
                data = json.load(f)
                return data.get('items', [])
        except Exception as e:
            logger.error("Failed to read shortlist",
                        error=str(e))
            return []
    
    def run(self) -> None:
        """Run the content update loop."""
        logger.info("Starting content manager")
        
        while self.should_run:
            try:
                # Run git pull to get latest changes
                subprocess.run(['git', 'pull', '--rebase'],
                            cwd='/app/data',
                            capture_output=True)
                
                # Read and update content
                items = self.read_shortlist()
                self.update_playlist(items)
                
            except Exception as e:
                logger.error("Error in content update loop",
                           error=str(e))
            
            time.sleep(30)  # Check for updates every 30 seconds

def main():
    """Main entry point for the live streaming renderer."""
    try:
        logger.log_startup()
        
        # Initialize configuration
        config = StreamConfig()
        
        # Start content manager
        content_manager = ContentManager(config)
        content_manager.start()
        
        # Start FFmpeg manager
        ffmpeg_manager = FFmpegManager(config)
        
        # Monitor the stream
        ffmpeg_manager.monitor_stream()
        
    except Exception as e:
        logger.error("Fatal error in live streamer",
                    error=str(e))
        raise
    finally:
        logger.log_shutdown()

if __name__ == '__main__':
    main()