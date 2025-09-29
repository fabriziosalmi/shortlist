# Video Renderer Plugin Development Guide

The Shortlist video renderer supports a plugin system that allows you to customize and enhance the video output. Plugins can modify the visual appearance, add overlays, create transitions between scenes, or implement any other video processing functionality.

## Plugin System Overview

Plugins are Python modules that extend the `VideoPlugin` base class. Each plugin can implement one or more hooks that are called at different points during video generation:

1. `on_startup()`: Called when the renderer starts, used to initialize resources
2. `on_before_render()`: Called before rendering begins to modify global settings
3. `process_frame()`: Called for each video frame to apply effects
4. `create_transition()`: Called between scenes to add transition effects
5. `finalize_video()`: Called after video assembly to add final effects
6. `on_shutdown()`: Called when the renderer stops, used to clean up resources

## Creating a New Plugin

1. Create a new Python file in the `renderers/video/plugins/` directory
2. Name the file with a descriptive name (e.g., `my_plugin.py`)
3. Implement the `Plugin` class that inherits from `VideoPlugin`
4. Override the hooks you want to use

### Plugin Template

```python path=null start=null
from PIL import Image
from moviepy.editor import VideoFileClip, CompositeVideoClip
from .base import VideoPlugin, RenderContext

class Plugin(VideoPlugin):
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
    
    def on_before_render(self, context: RenderContext) -> RenderContext:
        """Modify the global render context."""
        # Change global settings like fonts, colors, dimensions
        context.font_color = "#FF0000"  # Example: Change text color to red
        return context
    
    def process_frame(self, image: Image.Image, item_number: int,
                     is_transition: bool = False) -> Image.Image:
        """Process a single frame."""
        # Modify the frame using PIL operations
        return image
    
    def create_transition(self, prev_frame: Optional[Image.Image],
                         next_frame: Optional[Image.Image],
                         duration: float) -> Optional[VideoFileClip]:
        """Create a transition between scenes."""
        # Return None for no transition, or a VideoFileClip for custom transition
        return None
    
    def finalize_video(self, clip: CompositeVideoClip) -> CompositeVideoClip:
        """Add final effects to the complete video."""
        return clip
    
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

### on_before_render()
- Called before rendering begins
- Receives and returns a `RenderContext` object
- Modify global settings that affect all frames:
  - Font family and size
  - Colors
  - Video dimensions
  - Background images
  - Frame rate

### process_frame()
- Called for each frame in the video
- Receives:
  - A PIL Image to process
  - The 1-based item number
  - Whether the frame is part of a transition
- Can modify the frame using PIL operations
- Must return a PIL Image

### create_transition()
- Called between items to create transition effects
- Receives:
  - The last frame of the previous scene (None at start)
  - The first frame of the next scene (None at end)
  - Duration in seconds
- Return `None` for no transition, or a `VideoFileClip` for custom effect

### finalize_video()
- Called after video assembly but before final export
- Receives the complete `CompositeVideoClip`
- Use to add final effects or overlays
- Must return a `CompositeVideoClip`

### on_shutdown()
- Called when the renderer stops
- Use to clean up resources
- Log any errors that occur

## Plugin Configuration

Plugins are configured in the task's section of `schedule.json`:

```json path=null start=null
{
  "id": "youtube_video_stream",
  "type": "video",
  "priority": 5,
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
   - Use efficient PIL/moviepy operations
   - Consider using numpy for complex frame manipulation

4. **Video Processing**:
   - Process frames in RGB mode (convert from/to RGBA as needed)
   - Be mindful of alpha channel handling
   - Use moviepy for complex effects
   - Keep transitions short (0.5-1.0 seconds)

5. **Logging**:
   - Use structured logging via `self.logger`
   - Include relevant context in log entries
   - Use appropriate log levels (info/warning/error)

## Example Plugins

### Visual Theme
See `visual_theme.py` for an example of:
- Loading and validating theme settings
- Modifying global render context
- Handling fonts and colors
- Using background images

### Watermark
See `watermark.py` for an example of:
- Loading and scaling images
- Alpha channel manipulation
- Frame processing with PIL
- Position calculation

### Fade Transitions
See `fade_transition.py` for an example of:
- Creating transition effects
- Working with moviepy
- Frame blending
- Duration handling

## Adding Your Plugin

1. Create your plugin file in the plugins directory
2. Update the task's configuration in `schedule.json`
3. Rebuild the video renderer container:
   ```bash path=null start=null
   docker build -t shortlist-video-renderer renderers/video/
   ```
4. Start the renderer to test your plugin

## Testing Your Plugin

1. Create a short test shortlist with 2-3 items
2. Enable your plugin in the configuration
3. Monitor the renderer logs for errors
4. Check the generated video for:
   - Visual quality
   - Smooth transitions
   - Correct timing
   - Resource usage

## Common Issues

1. **Frame Processing**:
   - Always return frames in RGB mode
   - Keep original image dimensions
   - Handle alpha channels properly

2. **Transitions**:
   - Keep durations reasonable (0.5-1.0s)
   - Ensure smooth blending
   - Handle edge cases (first/last frame)