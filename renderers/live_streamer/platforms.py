"""
Streaming platform implementations for Shortlist live streamer.

This module provides platform-specific configurations and optimizations
for various streaming services (YouTube, Twitch, Facebook, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class StreamingQuality:
    """Represents streaming quality settings."""
    resolution: str
    framerate: int
    video_bitrate: str
    audio_bitrate: str
    audio_channels: int = 2
    audio_sample_rate: int = 44100
    keyframe_interval: int = 2  # seconds
    x264_preset: str = "veryfast"
    pixel_format: str = "yuv420p"

class StreamingPlatform(ABC):
    """Base class for streaming platform implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def get_rtmp_url(self) -> str:
        """Get the full RTMP URL including stream key."""
        pass
    
    @abstractmethod
    def get_recommended_quality(self) -> StreamingQuality:
        """Get recommended quality settings for this platform."""
        pass
    
    def get_ffmpeg_options(self) -> List[str]:
        """Get platform-specific FFmpeg options."""
        quality = self.get_recommended_quality()
        return [
            # Video settings
            "-c:v", "libx264",
            "-preset", quality.x264_preset,
            "-b:v", quality.video_bitrate,
            "-maxrate", quality.video_bitrate,
            "-bufsize", str(int(quality.video_bitrate.replace('k', '')) * 2) + 'k',
            "-pix_fmt", quality.pixel_format,
            "-g", str(quality.framerate * quality.keyframe_interval),
            "-keyint_min", str(quality.framerate),
            "-r", str(quality.framerate),
            
            # Audio settings
            "-c:a", "aac",
            "-b:a", quality.audio_bitrate,
            "-ar", str(quality.audio_sample_rate),
            "-ac", str(quality.audio_channels)
        ]
    
    def _validate_config(self) -> None:
        """Validate platform-specific configuration."""
        required_fields = ['stream_key_secret_name']
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field: {field}")

class YouTubeLive(StreamingPlatform):
    """YouTube Live streaming implementation."""
    
    RTMP_BASE = "rtmp://a.rtmp.youtube.com/live2"
    
    def get_rtmp_url(self) -> str:
        stream_key = self.config.get('stream_key', '')
        return f"{self.RTMP_BASE}/{stream_key}"
    
    def get_recommended_quality(self) -> StreamingQuality:
        # YouTube recommended settings
        return StreamingQuality(
            resolution="1280x720",
            framerate=30,
            video_bitrate="3000k",
            audio_bitrate="128k",
            keyframe_interval=2
        )

class TwitchTV(StreamingPlatform):
    """Twitch.tv streaming implementation."""
    
    RTMP_BASE = "rtmp://live.twitch.tv/app"
    
    def get_rtmp_url(self) -> str:
        stream_key = self.config.get('stream_key', '')
        return f"{self.RTMP_BASE}/{stream_key}"
    
    def get_recommended_quality(self) -> StreamingQuality:
        # Twitch recommended settings
        return StreamingQuality(
            resolution="1920x1080",
            framerate=60,
            video_bitrate="6000k",
            audio_bitrate="160k",
            audio_sample_rate=48000,
            keyframe_interval=2
        )

class FacebookLive(StreamingPlatform):
    """Facebook Live streaming implementation."""
    
    RTMP_BASE = "rtmps://live-api-s.facebook.com:443/rtmp"
    
    def get_rtmp_url(self) -> str:
        stream_key = self.config.get('stream_key', '')
        return f"{self.RTMP_BASE}/{stream_key}"
    
    def get_recommended_quality(self) -> StreamingQuality:
        # Facebook recommended settings
        return StreamingQuality(
            resolution="1280x720",
            framerate=30,
            video_bitrate="4000k",
            audio_bitrate="128k",
            keyframe_interval=2
        )
    
    def get_ffmpeg_options(self) -> List[str]:
        # Facebook requires specific options
        options = super().get_ffmpeg_options()
        options.extend([
            "-profile:v", "main",
            "-level", "3.1",
        ])
        return options

class VimeoLive(StreamingPlatform):
    """Vimeo Live streaming implementation."""
    
    def get_rtmp_url(self) -> str:
        # Vimeo provides unique RTMP URLs per stream
        rtmp_url = self.config.get('rtmp_url', '')
        stream_key = self.config.get('stream_key', '')
        return f"{rtmp_url}/{stream_key}"
    
    def get_recommended_quality(self) -> StreamingQuality:
        # Vimeo recommended settings
        return StreamingQuality(
            resolution="1920x1080",
            framerate=30,
            video_bitrate="5000k",
            audio_bitrate="192k",
            audio_sample_rate=48000,
            keyframe_interval=2
        )

class LinkedInLive(StreamingPlatform):
    """LinkedIn Live streaming implementation."""
    
    def get_rtmp_url(self) -> str:
        # LinkedIn provides custom RTMP URLs
        rtmp_url = self.config.get('rtmp_url', '')
        stream_key = self.config.get('stream_key', '')
        return f"{rtmp_url}/{stream_key}"
    
    def get_recommended_quality(self) -> StreamingQuality:
        # LinkedIn recommended settings
        return StreamingQuality(
            resolution="1920x1080",
            framerate=30,
            video_bitrate="4000k",
            audio_bitrate="128k",
            keyframe_interval=2
        )

# Factory for creating platform instances
PLATFORM_MAPPING = {
    'youtube': YouTubeLive,
    'twitch': TwitchTV,
    'facebook': FacebookLive,
    'vimeo': VimeoLive,
    'linkedin': LinkedInLive
}

def create_platform(platform_type: str, config: Dict[str, Any]) -> StreamingPlatform:
    """Create a streaming platform instance."""
    platform_class = PLATFORM_MAPPING.get(platform_type.lower())
    if not platform_class:
        raise ValueError(f"Unsupported platform: {platform_type}")
    
    return platform_class(config)