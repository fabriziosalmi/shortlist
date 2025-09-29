import os
from pathlib import Path
from typing import Optional
from PIL import Image
from .base import VideoPlugin, RenderContext

class Plugin(VideoPlugin):
    """Plugin that customizes the visual appearance of the video.
    
    Configuration in schedule.json:
    {
        "name": "visual_theme",
        "enabled": true,
        "settings": {
            "font_color": "#FFFFFF",
            "background_image": "background.jpg",
            "font_family": "Helvetica-Bold"
        }
    }
    """
    
    def __init__(self, settings: dict, logger):
        super().__init__(settings, logger)
        self.background_image: Optional[Image.Image] = None
        
    def on_startup(self) -> bool:
        """Load and validate theme resources."""
        try:
            # Validate color format
            font_color = self.settings.get('font_color', '#FFFFFF')
            if not font_color.startswith('#') or len(font_color) != 7:
                self.logger.error("Invalid font_color format",
                              color=font_color)
                return False
            
            # Load background image if specified
            bg_image = self.settings.get('background_image')
            if bg_image:
                plugin_dir = Path(__file__).parent
                bg_path = plugin_dir / bg_image
                
                if not bg_path.exists():
                    self.logger.error("Background image not found",
                                  path=str(bg_path))
                    return False
                    
                try:
                    self.background_image = Image.open(bg_path)
                    self.logger.info("Background image loaded",
                                 size=self.background_image.size)
                except Exception as e:
                    self.logger.error("Failed to load background image",
                                  error=str(e),
                                  error_type=type(e).__name__)
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error("Theme initialization failed",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def on_before_render(self, context: RenderContext) -> RenderContext:
        """Apply theme settings to the render context."""
        # Update font settings
        if font := self.settings.get('font_family'):
            context.font_family = font
            
        if color := self.settings.get('font_color'):
            context.font_color = color
            
        # Set background image path if loaded
        if self.background_image:
            # Save to a temporary file that the renderer can access
            temp_bg = "/tmp/theme_background.png"
            self.background_image.save(temp_bg)
            context.background_image = temp_bg
            
        return context
    
    def on_shutdown(self) -> None:
        """Clean up temporary files."""
        if os.path.exists("/tmp/theme_background.png"):
            os.unlink("/tmp/theme_background.png")