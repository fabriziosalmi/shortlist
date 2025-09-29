from pathlib import Path
from typing import Tuple
from PIL import Image, ImageEnhance
from .base import VideoPlugin, RenderContext

class Plugin(VideoPlugin):
    """Plugin that adds a watermark to the video.
    
    Configuration in schedule.json:
    {
        "name": "watermark",
        "enabled": true,
        "settings": {
            "image": "logo.png",
            "position": "bottom_right",  # top_left, top_right, bottom_left, bottom_right, center
            "opacity": 0.7,  # 0.0 to 1.0
            "margin": 20,  # pixels from edge
            "max_width": 200  # maximum width in pixels, height scaled proportionally
        }
    }
    """
    
    def __init__(self, settings: dict, logger):
        super().__init__(settings, logger)
        self.watermark: Image.Image = None
        
    def on_startup(self) -> bool:
        """Load and validate the watermark image."""
        try:
            # Validate settings
            if not self.settings.get('image'):
                self.logger.error("No watermark image specified")
                return False
                
            opacity = self.settings.get('opacity', 0.7)
            if not 0 <= opacity <= 1:
                self.logger.error("Invalid opacity (must be 0-1)",
                              opacity=opacity)
                return False
                
            position = self.settings.get('position', 'bottom_right')
            if position not in {'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center'}:
                self.logger.error("Invalid position",
                              position=position)
                return False
            
            # Load watermark image
            plugin_dir = Path(__file__).parent
            image_path = plugin_dir / self.settings['image']
            
            if not image_path.exists():
                self.logger.error("Watermark image not found",
                              path=str(image_path))
                return False
                
            self.watermark = Image.open(image_path).convert('RGBA')
            
            # Resize if needed
            max_width = self.settings.get('max_width', 200)
            if self.watermark.width > max_width:
                ratio = max_width / self.watermark.width
                new_size = (max_width, int(self.watermark.height * ratio))
                self.watermark = self.watermark.resize(new_size, Image.Resampling.LANCZOS)
            
            # Adjust opacity
            if opacity < 1:
                alpha = self.watermark.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
                self.watermark.putalpha(alpha)
            
            self.logger.info("Watermark loaded successfully",
                         size=self.watermark.size)
            return True
            
        except Exception as e:
            self.logger.error("Failed to initialize watermark",
                          error=str(e),
                          error_type=type(e).__name__)
            return False
    
    def get_watermark_position(self, frame_size: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate the position for the watermark."""
        margin = self.settings.get('margin', 20)
        position = self.settings.get('position', 'bottom_right')
        
        frame_w, frame_h = frame_size
        mark_w, mark_h = self.watermark.size
        
        if position == 'top_left':
            return (margin, margin)
        elif position == 'top_right':
            return (frame_w - mark_w - margin, margin)
        elif position == 'bottom_left':
            return (margin, frame_h - mark_h - margin)
        elif position == 'bottom_right':
            return (frame_w - mark_w - margin, frame_h - mark_h - margin)
        else:  # center
            return ((frame_w - mark_w) // 2, (frame_h - mark_h) // 2)
    
    def process_frame(self, image: Image.Image, item_number: int, is_transition: bool = False) -> Image.Image:
        """Add watermark to the frame."""
        if not self.watermark:
            return image
            
        # Convert to RGBA to support alpha
        result = image.convert('RGBA')
        
        # Calculate position
        pos = self.get_watermark_position(result.size)
        
        # Paste watermark using alpha compositing
        result.alpha_composite(self.watermark, pos)
        
        # Convert back to RGB for video
        return result.convert('RGB')