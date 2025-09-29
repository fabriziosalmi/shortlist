from pathlib import Path
from pydub import AudioSegment
from .base import AudioPlugin

class Plugin(AudioPlugin):
    """Plugin that adds sound effects between shortlist items.
    
    Configuration in schedule.json:
    {
        "name": "sound_effect_transition",
        "enabled": true,
        "settings": {
            "effect_sound": "chime.wav"  # Sound file in the plugin directory
        }
    }
    """
    
    def __init__(self, settings: dict, logger):
        super().__init__(settings, logger)
        self.transition_sound = None
    
    def on_startup(self) -> bool:
        """Load the transition sound effect."""
        try:
            # Validate settings
            if not self.settings.get('effect_sound'):
                self.logger.error("No effect_sound provided in settings")
                return False
            
            # Get path to the sound file (in plugin directory)
            plugin_dir = Path(__file__).parent
            sound_path = plugin_dir / self.settings['effect_sound']
            
            if not sound_path.exists():
                self.logger.error("Sound effect file not found",
                              path=str(sound_path))
                return False
            
            # Load the audio
            self.transition_sound = AudioSegment.from_file(str(sound_path))
            
            self.logger.info("Transition sound loaded successfully",
                         duration_ms=len(self.transition_sound))
            return True
            
        except Exception as e:
            self.logger.error("Failed to load transition sound",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def insert_between_segments(self, prev_item: Optional[int], next_item: Optional[int]) -> Optional[AudioSegment]:
        """Insert the sound effect between items."""
        # Don't insert at the very start or end of the shortlist
        if prev_item is None or next_item is None:
            return None
        
        return self.transition_sound if self.transition_sound else None