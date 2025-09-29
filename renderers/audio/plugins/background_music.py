import tempfile
import requests
from pathlib import Path
from pydub import AudioSegment
from .base import AudioPlugin

class Plugin(AudioPlugin):
    """Plugin that mixes background music with the TTS audio.
    
    Configuration in schedule.json:
    {
        "name": "background_music",
        "enabled": true,
        "settings": {
            "source_url": "URL to an MP3 file",
            "volume_percent": 15  # Volume level 0-100%
        }
    }
    """
    
    def __init__(self, settings: dict, logger):
        super().__init__(settings, logger)
        self.background_music = None
        self.position = 0
        
    def on_startup(self) -> bool:
        """Download and load the background music file."""
        try:
            # Validate settings
            if not self.settings.get('source_url'):
                self.logger.error("No source_url provided in settings")
                return False
                
            volume = self.settings.get('volume_percent', 15)
            if not 0 <= volume <= 100:
                self.logger.error("Invalid volume_percent (must be 0-100)",
                              volume=volume)
                return False
                
            # Download the music file
            with log_operation(self.logger, "download_music",
                           url=self.settings['source_url']):
                response = requests.get(self.settings['source_url'])
                response.raise_for_status()
                
                # Save to a temporary file
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    tmp.write(response.content)
                    tmp_path = Path(tmp.name)
            
            # Load the audio
            self.background_music = AudioSegment.from_mp3(tmp_path)
            
            # Adjust volume
            self.background_music = self.background_music - (20 * (1 - volume/100))
            
            # Clean up the temp file
            tmp_path.unlink()
            
            self.logger.info("Background music loaded successfully",
                         duration_ms=len(self.background_music))
            return True
            
        except Exception as e:
            self.logger.error("Failed to load background music",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def process_audio_segment(self, audio_segment: AudioSegment, item_number: int) -> AudioSegment:
        """Mix background music with the TTS audio segment."""
        if not self.background_music:
            return audio_segment
            
        # Get the portion of background music we need
        segment_length = len(audio_segment)
        music_length = len(self.background_music)
        
        # If we need more music than we have, loop it
        if self.position + segment_length > music_length:
            self.position = 0
            
        music_segment = self.background_music[self.position:self.position + segment_length]
        
        # If the music segment is shorter than our TTS audio, loop it
        while len(music_segment) < segment_length:
            remaining = segment_length - len(music_segment)
            music_segment += self.background_music[0:remaining]
            
        self.position = (self.position + segment_length) % music_length
        
        # Overlay the audio
        return audio_segment.overlay(music_segment)