import numpy as np
from PIL import Image
from moviepy.editor import ImageClip, VideoClip
from typing import Optional
from .base import VideoPlugin

class Plugin(VideoPlugin):
    """Plugin that creates fade transitions between scenes.
    
    Configuration in schedule.json:
    {
        "name": "fade_transition",
        "enabled": true,
        "settings": {
            "duration_seconds": 0.5,  # Duration of the fade
            "type": "crossfade"  # crossfade, fade_to_black, or fade_from_black
        }
    }
    """
    
    def __init__(self, settings: dict, logger):
        super().__init__(settings, logger)
        self.prev_frame_clip = None
        self.next_frame_clip = None
    
    def on_startup(self) -> bool:
        """Validate transition settings."""
        try:
            duration = self.settings.get('duration_seconds', 0.5)
            if duration <= 0:
                self.logger.error("Invalid duration",
                              duration=duration)
                return False
                
            transition_type = self.settings.get('type', 'crossfade')
            if transition_type not in {'crossfade', 'fade_to_black', 'fade_from_black'}:
                self.logger.error("Invalid transition type",
                              type=transition_type)
                return False
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize fade transition",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def create_fade_frame(self, frame1: np.ndarray, frame2: np.ndarray, progress: float) -> np.ndarray:
        """Create an intermediate frame for the fade effect.
        
        Args:
            frame1: First frame as numpy array
            frame2: Second frame as numpy array
            progress: Float from 0 to 1 indicating transition progress
            
        Returns:
            Blended frame as numpy array
        """
        return (frame1 * (1 - progress) + frame2 * progress).astype('uint8')
    
    def create_transition(self, prev_frame: Optional[Image.Image], next_frame: Optional[Image.Image],
                         duration: float) -> Optional[VideoClip]:
        """Generate a fade transition between frames."""
        # Get settings
        fade_duration = self.settings.get('duration_seconds', 0.5)
        fade_type = self.settings.get('type', 'crossfade')
        
        # Convert frames to numpy arrays
        if prev_frame:
            prev_array = np.array(prev_frame)
        if next_frame:
            next_array = np.array(next_frame)
        
        def make_frame(t):
            # Calculate progress through the transition (0 to 1)
            progress = t / fade_duration
            
            if fade_type == 'crossfade' and prev_frame and next_frame:
                # Blend between frames
                return self.create_fade_frame(prev_array, next_array, progress)
                
            elif fade_type == 'fade_to_black' and prev_frame:
                # Fade out to black
                black = np.zeros_like(prev_array)
                return self.create_fade_frame(prev_array, black, progress)
                
            elif fade_type == 'fade_from_black' and next_frame:
                # Fade in from black
                black = np.zeros_like(next_array)
                return self.create_fade_frame(black, next_array, progress)
            
            # Fallback: no transition
            return next_array if next_frame else prev_array
        
        # Create the transition clip
        clip = VideoClip(make_frame, duration=fade_duration)
        
        self.logger.info("Created fade transition",
                      type=fade_type,
                      duration=fade_duration)
        return clip