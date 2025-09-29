from abc import ABC, abstractmethod
from typing import Optional
from pydub import AudioSegment
from utils.logging_config import ComponentLogger

class AudioPlugin(ABC):
    """Base class for audio renderer plugins.
    
    This class defines the interface that all audio plugins must implement.
    Plugins can modify the audio stream by implementing one or more hooks.
    """
    
    def __init__(self, settings: dict, logger: ComponentLogger):
        """Initialize the plugin with its settings.
        
        Args:
            settings: Plugin-specific settings from schedule.json
            logger: Logger instance for structured logging
        """
        self.settings = settings
        self.logger = logger
    
    def on_startup(self) -> bool:
        """Called when the renderer starts.
        
        Use this to initialize resources, download files, etc.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        return True
    
    def process_audio_segment(self, audio_segment: AudioSegment, item_number: int) -> AudioSegment:
        """Process an audio segment before it's added to the final output.
        
        Args:
            audio_segment: The audio segment to process
            item_number: The 1-based index of the current shortlist item
            
        Returns:
            AudioSegment: The processed audio segment
        """
        return audio_segment
    
    def insert_between_segments(self, prev_item: Optional[int], next_item: Optional[int]) -> Optional[AudioSegment]:
        """Generate audio to insert between shortlist items.
        
        Args:
            prev_item: The 1-based index of the previous item (None at start)
            next_item: The 1-based index of the next item (None at end)
            
        Returns:
            Optional[AudioSegment]: Audio to insert, or None for default silence
        """
        return None
    
    def on_shutdown(self) -> None:
        """Called when the renderer shuts down.
        
        Use this to clean up any resources.
        """
        pass