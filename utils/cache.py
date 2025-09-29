"""
Cache management utilities for Shortlist renderers.

This module provides functionality for caching rendered segments
and managing the cache lifecycle.
"""

import os
import json
import time
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class SegmentCache:
    """Manages caching of rendered segments."""
    
    def __init__(
        self,
        cache_dir: str,
        max_age_days: int = 30,
        min_free_space_mb: int = 1000
    ):
        """Initialize the segment cache.
        
        Args:
            cache_dir: Base directory for cache storage
            max_age_days: Maximum age of cached files before cleanup
            min_free_space_mb: Minimum free space to maintain
        """
        self.cache_dir = Path(cache_dir)
        self.segments_dir = self.cache_dir / 'segments'
        self.assets_dir = self.cache_dir / 'assets'
        self.max_age_seconds = max_age_days * 24 * 60 * 60
        self.min_free_space = min_free_space_mb * 1024 * 1024  # Convert to bytes
        
        # Create cache directories
        self.segments_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        
        # Initialize cache stats
        self._cache_hits = 0
        self._cache_misses = 0
    
    def generate_item_hash(self, item: Dict[str, Any]) -> str:
        """Generate a stable hash for an item.
        
        The hash is based on a canonicalized JSON representation of the item,
        ensuring consistent results regardless of dict key ordering.
        
        Args:
            item: The item to hash
        
        Returns:
            A hex string hash of the item
        """
        # Create a canonical JSON representation
        canonical = json.dumps(item, sort_keys=True, ensure_ascii=True)
        
        # Calculate SHA-256 hash
        hasher = hashlib.sha256(canonical.encode('utf-8'))
        
        # Return first 16 characters of hex digest
        return hasher.hexdigest()[:16]
    
    def get_segment_path(self, item: Dict[str, Any], extension: str = '.mp4') -> Path:
        """Get the cache path for an item's rendered segment.
        
        Args:
            item: The item to get path for
            extension: File extension for the segment
        
        Returns:
            Path object for the cached segment
        """
        item_hash = self.generate_item_hash(item)
        return self.segments_dir / f"{item_hash}{extension}"
    
    def get_asset_path(self, url: str, extension: Optional[str] = None) -> Path:
        """Get the cache path for a downloaded asset.
        
        Args:
            url: The source URL of the asset
            extension: Optional file extension override
        
        Returns:
            Path object for the cached asset
        """
        # Hash the URL for the filename
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
        
        # Use provided extension or extract from URL
        if not extension:
            extension = os.path.splitext(url)[1] or '.bin'
        
        return self.assets_dir / f"{url_hash}{extension}"
    
    def get_segment(
        self,
        item: Dict[str, Any],
        extension: str = '.mp4'
    ) -> Optional[Path]:
        """Try to get a cached segment for an item.
        
        Args:
            item: The item to look up
            extension: Expected file extension
        
        Returns:
            Path to cached segment if found, None otherwise
        """
        segment_path = self.get_segment_path(item, extension)
        
        if segment_path.exists():
            # Update access time and stats
            os.utime(segment_path, None)
            self._cache_hits += 1
            logger.info("Cache hit",
                       item_id=item.get('id', 'unknown'),
                       cache_path=str(segment_path))
            return segment_path
        
        self._cache_misses += 1
        logger.info("Cache miss",
                   item_id=item.get('id', 'unknown'))
        return None
    
    def save_segment(
        self,
        item: Dict[str, Any],
        segment_path: Path,
        extension: str = '.mp4'
    ) -> Path:
        """Save a rendered segment to cache.
        
        Args:
            item: The source item
            segment_path: Path to the rendered segment
            extension: File extension for the segment
        
        Returns:
            Path where the segment was cached
        """
        cache_path = self.get_segment_path(item, extension)
        
        # Ensure we have enough space
        self._ensure_free_space(segment_path.stat().st_size)
        
        # Copy to cache
        shutil.copy2(segment_path, cache_path)
        logger.info("Cached new segment",
                   item_id=item.get('id', 'unknown'),
                   cache_path=str(cache_path))
        
        return cache_path
    
    def cleanup(self) -> None:
        """Clean up old cache entries."""
        logger.info("Starting cache cleanup")
        current_time = time.time()
        
        # Clean segments
        for path in self.segments_dir.glob('*'):
            if not path.is_file():
                continue
            
            age = current_time - path.stat().st_atime
            if age > self.max_age_seconds:
                try:
                    path.unlink()
                    logger.info("Removed old cache file",
                              path=str(path),
                              age_days=age/86400)
                except Exception as e:
                    logger.error("Failed to remove cache file",
                               error=str(e),
                               path=str(path))
        
        # Clean assets (same logic)
        for path in self.assets_dir.glob('*'):
            if not path.is_file():
                continue
            
            age = current_time - path.stat().st_atime
            if age > self.max_age_seconds:
                try:
                    path.unlink()
                    logger.info("Removed old asset file",
                              path=str(path),
                              age_days=age/86400)
                except Exception as e:
                    logger.error("Failed to remove asset file",
                               error=str(e),
                               path=str(path))
    
    def _ensure_free_space(self, needed_bytes: int) -> None:
        """Ensure enough free space is available.
        
        Removes oldest files if necessary.
        
        Args:
            needed_bytes: Number of bytes needed
        """
        while True:
            # Check free space
            free_space = shutil.disk_usage(self.cache_dir).free
            if free_space >= needed_bytes + self.min_free_space:
                return
            
            # Get list of files sorted by access time
            files = []
            for directory in [self.segments_dir, self.assets_dir]:
                files.extend(
                    (p, p.stat().st_atime)
                    for p in directory.glob('*')
                    if p.is_file()
                )
            
            if not files:
                raise IOError("No space available and no files to remove")
            
            # Remove oldest file
            oldest_file = min(files, key=lambda x: x[1])[0]
            try:
                oldest_file.unlink()
                logger.info("Removed old file to free space",
                          path=str(oldest_file))
            except Exception as e:
                logger.error("Failed to remove file",
                           error=str(e),
                           path=str(oldest_file))
                raise
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'total_requests': self._cache_hits + self._cache_misses,
            'hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses)
            if (self._cache_hits + self._cache_misses) > 0 else 0
        }