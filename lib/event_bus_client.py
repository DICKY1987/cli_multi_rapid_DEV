from __future__ import annotations

import os
from typing import Any, Dict

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dep
    requests = None  # type: ignore


def publish_event(event: Dict[str, Any]) -> bool:
    """Publish an event to the event-bus if configured.

    Configuration via env:
      - GDW_BROADCAST=1 to enable
      - EVENT_BUS_URL (default: http://127.0.0.1:8001/publish)
    Returns True if successfully sent or broadcasting disabled, False on failure.
    """
    if os.environ.get("GDW_BROADCAST", "") != "1":
        return True
    if requests is None:
        return False
    url = os.environ.get("EVENT_BUS_URL", "http://127.0.0.1:8001/publish").strip()
    try:
        resp = requests.post(url, json=event, timeout=1.5)
        return resp.ok
    except Exception:
        return False
