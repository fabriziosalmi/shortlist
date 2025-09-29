"""
Webhook system for Shortlist notifications.

This module implements the webhook subscription and notification system,
allowing external services to receive notifications when important events occur.
"""

import json
import uuid
import os
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, HttpUrl, Field, validator
from pythonjsonlogger import jsonlogger
import logging

# Configure logging
logger = logging.getLogger("webhook_manager")
json_handler = logging.FileHandler("/app/data/webhooks.log")
json_handler.setFormatter(jsonlogger.JsonFormatter())
logger.addHandler(json_handler)
logger.setLevel(logging.INFO)

class WebhookEvent(str, Enum):
    """Supported webhook event types."""
    SHORTLIST_UPDATED = "shortlist.updated"
    NODE_DOWN = "node.down"  # Future use
    NODE_UP = "node.up"      # Future use

class WebhookSubscription(BaseModel):
    """Model for a webhook subscription."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: HttpUrl
    event: WebhookEvent
    created_at: datetime = Field(default_factory=datetime.utcnow)
    description: Optional[str] = None
    
    @validator('url')
    def validate_url(cls, v):
        """Additional URL validation."""
        parsed = urlparse(str(v))
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('URL must use http or https scheme')
        return v

class WebhookPayload(BaseModel):
    """Model for webhook notification payloads."""
    event: WebhookEvent
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    triggered_by: str
    data: Dict[str, Any]

class WebhookManager:
    """Manages webhook subscriptions and notifications."""
    
    def __init__(self, storage_path: str = "/app/data/webhooks.json"):
        self.storage_path = storage_path
        self.subscriptions: List[WebhookSubscription] = []
        self._load_subscriptions()
        
        # Initialize async client for notifications
        self.client = httpx.AsyncClient(
            timeout=10.0,  # 10 second timeout
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    def _load_subscriptions(self) -> None:
        """Load webhook subscriptions from storage."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.subscriptions = [
                        WebhookSubscription(**sub)
                        for sub in data.get('subscriptions', [])
                    ]
                    logger.info("Loaded webhook subscriptions",
                              count=len(self.subscriptions))
        except Exception as e:
            logger.error("Failed to load webhook subscriptions",
                        error=str(e),
                        error_type=type(e).__name__)
            self.subscriptions = []
    
    def _save_subscriptions(self) -> None:
        """Save webhook subscriptions to storage."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            with open(self.storage_path, 'w') as f:
                json.dump({
                    'subscriptions': [
                        sub.dict() for sub in self.subscriptions
                    ]
                }, f, indent=2, default=str)
                
            logger.info("Saved webhook subscriptions",
                       count=len(self.subscriptions))
                
        except Exception as e:
            logger.error("Failed to save webhook subscriptions",
                        error=str(e),
                        error_type=type(e).__name__)
    
    def list_subscriptions(self) -> List[WebhookSubscription]:
        """List all webhook subscriptions."""
        return self.subscriptions
    
    def add_subscription(self, subscription: WebhookSubscription) -> WebhookSubscription:
        """Add a new webhook subscription."""
        self.subscriptions.append(subscription)
        self._save_subscriptions()
        logger.info("Added webhook subscription",
                   id=subscription.id,
                   url=str(subscription.url),
                   event=subscription.event)
        return subscription
    
    def remove_subscription(self, subscription_id: str) -> bool:
        """Remove a webhook subscription by ID."""
        initial_count = len(self.subscriptions)
        self.subscriptions = [
            s for s in self.subscriptions
            if s.id != subscription_id
        ]
        
        if len(self.subscriptions) < initial_count:
            self._save_subscriptions()
            logger.info("Removed webhook subscription",
                       subscription_id=subscription_id)
            return True
        return False
    
    def get_subscriptions_for_event(self, event: WebhookEvent) -> List[WebhookSubscription]:
        """Get all subscriptions for a specific event."""
        return [s for s in self.subscriptions if s.event == event]
    
    async def send_notification(
        self,
        event: WebhookEvent,
        data: Dict[str, Any],
        triggered_by: str
    ) -> None:
        """Send notifications to all subscribers of an event."""
        subscriptions = self.get_subscriptions_for_event(event)
        if not subscriptions:
            logger.debug("No subscriptions for event",
                        event=event)
            return
        
        # Prepare the payload
        payload = WebhookPayload(
            event=event,
            triggered_by=triggered_by,
            data=data
        )
        
        # Send notifications concurrently
        tasks = []
        for subscription in subscriptions:
            task = asyncio.create_task(
                self._send_single_notification(subscription, payload)
            )
            tasks.append(task)
        
        # Wait for all notifications to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_single_notification(
        self,
        subscription: WebhookSubscription,
        payload: WebhookPayload
    ) -> None:
        """Send a notification to a single webhook endpoint."""
        try:
            response = await self.client.post(
                str(subscription.url),
                json=payload.dict(),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code not in (200, 201, 202, 204):
                logger.warning("Webhook delivery failed",
                             subscription_id=subscription.id,
                             status_code=response.status_code,
                             response=response.text)
            else:
                logger.info("Webhook delivered successfully",
                          subscription_id=subscription.id,
                          event=payload.event)
                
        except Exception as e:
            logger.error("Webhook delivery error",
                        error=str(e),
                        error_type=type(e).__name__,
                        subscription_id=subscription.id)

class ChangeDetector(threading.Thread):
    """Background thread for detecting changes in shortlist.json."""
    
    def __init__(
        self,
        webhook_manager: WebhookManager,
        check_interval: int = 10,
        shortlist_path: str = "/app/data/shortlist.json"
    ):
        super().__init__(daemon=True)
        self.webhook_manager = webhook_manager
        self.check_interval = check_interval
        self.shortlist_path = shortlist_path
        self.last_known_hash = None
        self.running = True
    
    def _get_current_hash(self) -> Optional[str]:
        """Get the current Git hash of shortlist.json."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "-n", "1", "--pretty=format:%H", "--", self.shortlist_path],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            logger.error("Failed to get Git hash",
                        error=str(e))
            return None
    
    def _read_shortlist(self) -> Dict[str, Any]:
        """Read the current shortlist content."""
        try:
            with open(self.shortlist_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read shortlist",
                        error=str(e))
            return {}
    
    def run(self) -> None:
        """Run the change detection loop."""
        logger.info("Starting change detector")
        
        while self.running:
            try:
                # Pull latest changes
                subprocess.run(["git", "pull", "--rebase"],
                            capture_output=True)
                
                current_hash = self._get_current_hash()
                if current_hash and current_hash != self.last_known_hash:
                    logger.info("Detected shortlist change",
                              previous_hash=self.last_known_hash,
                              current_hash=current_hash)
                    
                    # Get current shortlist content
                    shortlist_data = self._read_shortlist()
                    
                    # Send notifications asynchronously
                    asyncio.run(
                        self.webhook_manager.send_notification(
                            WebhookEvent.SHORTLIST_UPDATED,
                            shortlist_data,
                            f"git_commit:{current_hash}"
                        )
                    )
                    
                    self.last_known_hash = current_hash
                
            except Exception as e:
                logger.error("Error in change detector",
                           error=str(e))
            
            # Wait for next check
            time.sleep(self.check_interval)
    
    def stop(self) -> None:
        """Stop the change detector thread."""
        self.running = False