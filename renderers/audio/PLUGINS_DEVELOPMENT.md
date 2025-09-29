# Audio Renderer Plugin Development Guide

The Shortlist audio renderer supports a plugin system that allows you to customize and enhance the audio output. Plugins can modify the TTS audio, add background music, insert sound effects between items, or implement any other audio processing functionality.

## Plugin System Overview

Plugins are Python modules that extend the `AudioPlugin` base class. Each plugin can implement one or more hooks that are called at different points during audio generation:

1. `on_startup()`: Called when the renderer starts, used to initialize resources
2. `process_audio_segment()`: Called for each TTS segment to modify the audio
3. `insert_between_segments()`: Called between items to add transition sounds
4. `on_shutdown()`: Called when the renderer stops, used to clean up resources

## Creating a New Plugin

1. Create a new Python file in the `renderers/audio/plugins/` directory
2. Name the file with a descriptive name (e.g., `my_plugin.py`)
3. Implement the `Plugin` class that inherits from `AudioPlugin`
4. Override the hooks you want to use

### Plugin Template

```python path=null start=null
from pydub import AudioSegment
from .base import AudioPlugin

class Plugin(AudioPlugin):
    """Your plugin description here.
    
    Configuration in schedule.json:
    {
        "name": "my_plugin",
        "enabled": true,
        "settings": {
            "setting1": "value1",
            "setting2": "value2"
        }
    }
    """
    
    def __init__(self, settings: dict, logger):
        super().__init__(settings, logger)
        # Initialize any plugin-specific state
        
    def on_startup(self) -> bool:
        """Initialize resources."""
        try:
            # Validate settings
            if not self.settings.get('required_setting'):
                self.logger.error("Missing required setting")
                return False
                
            # Initialize resources
            # ...
            
            return True
        except Exception as e:
            self.logger.error("Startup failed",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def process_audio_segment(self, audio_segment: AudioSegment, item_number: int) -> AudioSegment:
        """Modify the TTS audio for a shortlist item."""
        return audio_segment  # Return unmodified or process it
    
    def insert_between_segments(self, prev_item: Optional[int], next_item: Optional[int]) -> Optional[AudioSegment]:
        """Add audio between shortlist items."""
        return None  # Return None for default silence or an AudioSegment
    
    def on_shutdown(self) -> None:
        """Clean up resources."""
        pass
```

## Plugin Hooks in Detail

### on_startup()
- Called when the renderer initializes
- Use to validate settings and load resources (files, network resources, etc.)
- Return `True` if initialization succeeds, `False` if it fails
- Log errors using `self.logger`

### process_audio_segment()
- Called for each TTS-generated audio segment
- Receives the audio segment and its item number (1-based)
- Can modify the audio (e.g., add effects, change volume)
- Must return an AudioSegment

### insert_between_segments()
- Called between items, and at the start/end of the shortlist
- Receives the previous and next item numbers (can be None)
- Return `None` for default silence, or an AudioSegment to insert
- If multiple plugins return audio, they're mixed together

### on_shutdown()
- Called when the renderer stops
- Use to clean up resources
- Log any errors that occur

## Plugin Configuration

Plugins are configured in the task's section of `schedule.json`:

```json path=null start=null
{
  "id": "icecast_audio_stream",
  "type": "audio",
  "priority": 4,
  "config": {
    "plugins": [
      {
        "name": "my_plugin",
        "enabled": true,
        "settings": {
          "setting1": "value1",
          "setting2": "value2"
        }
      }
    ]
  }
}
```

Configuration fields:
- `name`: Must match your plugin's filename (without .py)
- `enabled`: Boolean to easily enable/disable the plugin
- `settings`: Plugin-specific configuration passed to `__init__`

## Best Practices

1. **Error Handling**: Always catch exceptions and log them properly:
   ```python path=null start=null
   try:
       # Your code
   except Exception as e:
       self.logger.error("Operation failed",
                      error=str(e),
                      error_type=type(e).__name__)
   ```

2. **Resource Management**:
   - Load resources in `on_startup()`
   - Clean up in `on_shutdown()`
   - Use context managers for file operations
   - Store temporary files in `/tmp/`

3. **Performance**:
   - Cache resources loaded in `on_startup()`
   - Avoid loading large files repeatedly
   - Process audio efficiently using pydub operations

4. **Logging**:
   - Use structured logging via `self.logger`
   - Include relevant context in log entries
   - Use appropriate log levels (info/warning/error)

## Example Plugins

### Background Music Plugin
See `background_music.py` for an example of:
- Downloading and caching audio files
- Volume adjustment
- Continuous background audio looping
- Network resource handling

### Sound Effect Transitions
See `sound_effect_transition.py` for an example of:
- Loading local audio files
- Adding effects between segments
- Simple audio mixing

## Adding Your Plugin

1. Create your plugin file in the plugins directory
2. Update the task's configuration in `schedule.json`
3. Rebuild the audio renderer container:
   ```bash path=null start=null
   docker build -t shortlist-audio-renderer renderers/audio/
   ```
4. Start the renderer to test your plugin