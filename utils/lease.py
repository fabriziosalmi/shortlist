"""
Task lease management for Shortlist.

This module handles the lease-based task assignment system, replacing
the old heartbeat-based approach for better Git efficiency.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Default lease duration (5 minutes)
# Lease timing configuration
class LeaseConfig:
    """Configuration for lease timing."""
    # Default durations
    DEFAULT_LEASE_DURATION = timedelta(minutes=5)
    MIN_LEASE_DURATION = timedelta(minutes=1)
    MAX_LEASE_DURATION = timedelta(minutes=30)
    
    # Renewal thresholds
    DEFAULT_RENEWAL_THRESHOLD = timedelta(minutes=1)
    MIN_RENEWAL_THRESHOLD = timedelta(seconds=30)
    MAX_RENEWAL_THRESHOLD = timedelta(minutes=5)
    
    # Network condition adjustments
    HIGH_LATENCY_LEASE_DURATION = timedelta(minutes=10)
    HIGH_LATENCY_RENEWAL_THRESHOLD = timedelta(minutes=2)
    
    @classmethod
    def get_timing_for_latency(cls, latency: float) -> Tuple[timedelta, timedelta]:
        """Get appropriate lease timing based on network latency.
        
        Args:
            latency: Observed network latency in seconds
        
        Returns:
            Tuple of (lease_duration, renewal_threshold)
        """
        if latency > 1.0:  # High latency environment
            return (cls.HIGH_LATENCY_LEASE_DURATION,
                    cls.HIGH_LATENCY_RENEWAL_THRESHOLD)
        return (cls.DEFAULT_LEASE_DURATION,
                cls.DEFAULT_RENEWAL_THRESHOLD)

# Renewal threshold (renew when less than 1 minute remains)
RENEWAL_THRESHOLD = timedelta(minutes=1)

def create_lease(duration: Optional[timedelta] = None) -> str:
    """Create a new lease with expiration timestamp.
    
    Args:
        duration: Optional lease duration (default: 5 minutes)
    
    Returns:
        ISO 8601 timestamp string when the lease expires
    """
    duration = duration or DEFAULT_LEASE_DURATION
    expiration = datetime.now(timezone.utc) + duration
    return expiration.isoformat()

def is_lease_expired(lease_expires_at: Optional[str], grace_period: timedelta = RENEWAL_THRESHOLD) -> bool:
    """Check if a lease has expired.
    
    Args:
        lease_expires_at: ISO 8601 timestamp string
        grace_period: Consider lease expired this much before actual expiration
    
    Returns:
        True if lease has expired or is invalid
    """
    if not lease_expires_at:
        return True
    
    try:
        expiration = datetime.fromisoformat(lease_expires_at)
        now = datetime.now(timezone.utc)
        return now + grace_period >= expiration
    except (ValueError, TypeError) as e:
        logger.warning("Invalid lease timestamp",
                      lease_expires_at=lease_expires_at,
                      error=str(e))
        return True

def calculate_sleep_time(lease_expires_at: str) -> float:
    """Calculate how long to sleep before lease renewal.
    
    Args:
        lease_expires_at: ISO 8601 timestamp string
    
    Returns:
        Number of seconds to sleep
    """
    try:
        expiration = datetime.fromisoformat(lease_expires_at)
        now = datetime.now(timezone.utc)
        renewal_time = expiration - RENEWAL_THRESHOLD
        
        # Calculate sleep duration
        sleep_seconds = (renewal_time - now).total_seconds()
        return max(0, sleep_seconds)  # Don't return negative sleep time
        
    except (ValueError, TypeError) as e:
        logger.error("Failed to calculate sleep time",
                    lease_expires_at=lease_expires_at,
                    error=str(e))
        return 0  # Return 0 on error to trigger immediate renewal

def extend_lease(
    task: Dict[str, Any],
    duration: Optional[timedelta] = None
) -> Dict[str, Any]:
    """Create updated task assignment with extended lease.
    
    Args:
        task: Current task assignment
        duration: Optional new lease duration
    
    Returns:
        Updated task assignment dict with new lease expiration
    """
    updated_task = task.copy()
    updated_task['lease_expires_at'] = create_lease(duration)
    
    if 'task_heartbeat' in updated_task:
        del updated_task['task_heartbeat']  # Remove old heartbeat field
        
    return updated_task