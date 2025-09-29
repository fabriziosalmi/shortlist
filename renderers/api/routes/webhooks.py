"""
Webhook management routes for the Shortlist API.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_maintainer_token
from ..webhooks import WebhookManager, WebhookSubscription, WebhookEvent

# Initialize router
router = APIRouter(prefix="/v1/admin/webhooks", tags=["webhooks"])

# Initialize webhook manager
webhook_manager = WebhookManager()

@router.get("/", response_model=List[WebhookSubscription])
async def list_webhooks(_: str = Depends(get_maintainer_token)):
    """List all webhook subscriptions."""
    return webhook_manager.list_subscriptions()

@router.post("/", response_model=WebhookSubscription)
async def create_webhook(
    subscription: WebhookSubscription,
    _: str = Depends(get_maintainer_token)
):
    """Create a new webhook subscription."""
    return webhook_manager.add_subscription(subscription)

@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    _: str = Depends(get_maintainer_token)
):
    """Delete a webhook subscription."""
    if webhook_manager.remove_subscription(webhook_id):
        return {"message": "Webhook subscription removed"}
    raise HTTPException(status_code=404, detail="Webhook subscription not found")