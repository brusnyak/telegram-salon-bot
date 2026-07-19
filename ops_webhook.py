import json
import logging
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def send_to_ops_lab(webhook_url: str, event_id: str, sender_name: str, sender_handle: str, message: str):
    """Post an event to the messaging-bot-ops-lab backend."""
    payload = json.dumps({
        "update_id": hash(event_id) & 0x7FFFFFFF,
        "message": {
            "date": int(datetime.now(timezone.utc).timestamp()),
            "chat": {
                "id": hash(sender_handle) & 0x7FFFFFFF,
                "type": "private",
                "username": sender_handle.lstrip("@"),
                "first_name": sender_name,
            },
            "text": message,
        },
    }).encode()

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        logger.warning("ops-lab webhook failed: %s", exc)
