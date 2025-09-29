from abc import ABC
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip

@dataclass
class RenderContext:
    """Context object containing global rendering settings and resources."""
    font_family: str = "DejaVuSans"
    font_size: int = 60
    font_color: str = "#FFFFFF"
    background_color: str = "#000000"
    background_image: Optional[str] = None
    video_width: int = 1280
    video_height: int = 720
    fps: int = 24
    
    def get_font(self) -> ImageFont:
        """Get the configured font."""
        try:
            return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{self.font_family}.ttf", self.font_size)
        except:
            return ImageFont.load_default()

class VideoPlugin(ABC):
    """Base class for video renderer plugins.
    
    This class defines the interface that all video plugins must implement.
    Plugins can modify the rendering process by implementing one or more hooks.
    """
    
    def __init__(self, settings: Dict[str, Any], logger):
        """Initialize the plugin with its settings.
        
        Args:
            settings: Plugin-specific settings from schedule.json
            logger: Logger instance for structured logging
        """
        self.settings = settings
        self.logger = logger
    
    def on_startup(self) -> bool:
        """Called when the renderer starts.
        
        Use this to validate settings and initialize resources.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        return True
    
    def on_before_render(self, context: RenderContext) -> RenderContext:
        """Called before rendering begins to modify the global context.
        
        This is where you can modify global rendering settings like fonts,
        colors, dimensions, etc.
        
        Args:
            context: The current render context
            
        Returns:
            RenderContext: The modified context
        """
        return context
    
    def process_frame(self, image: Image.Image, item_number: int, is_transition: bool = False) -> Image.Image:
        """Process a single frame before it's added to the video.
        
        Args:
            image: The PIL Image to process
            item_number: The 1-based index of the current shortlist item
            is_transition: Whether this frame is part of a transition
            
        Returns:
            Image.Image: The processed frame
        """
        return image
    
    def create_transition(self, prev_frame: Optional[Image.Image], next_frame: Optional[Image.Image], 
                         duration: float) -> Optional[VideoFileClip]:
        """Generate a transition effect between two frames.
        
        Args:
            prev_frame: The last frame of the previous scene (None at start)
            next_frame: The first frame of the next scene (None at end)
            duration: How long the transition should last in seconds
            
        Returns:
            Optional[VideoFileClip]: A video clip for the transition, or None to use a cut
        """
        return None
    
    def finalize_video(self, clip: CompositeVideoClip) -> CompositeVideoClip:
        """Called after the main video is assembled but before final export.
        
        Use this to add final effects or overlays to the entire video.
        
        Args:
            clip: The complete video clip
            
        Returns:
            CompositeVideoClip: The modified video clip
        """
        return clip
    
    def on_shutdown(self) -> None:
        """Called when the renderer shuts down.
        
        Use this to clean up any resources.
        """
        pass