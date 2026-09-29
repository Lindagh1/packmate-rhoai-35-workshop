"""Server-Sent Events helpers for Packmate streaming chat."""

from __future__ import annotations

import json
import re
from typing import Any

_THINK_RE = re.compile(
    r"<think>.*?</think>|<thinking>.*?</thinking>",
    re.IGNORECASE | re.DOTALL,
)
_STACK_RE = re.compile(r"Traceback \(most recent call last\):.*", re.DOTALL)
_SENSITIVE_RE = re.compile(
    r"(medical|insulin|accessibility.?notes?|api[_-]?key|bearer\s+\S+|password)",
    re.IGNORECASE,
)


def format_sse(event: str, data: dict[str, Any] | str) -> str:
    """Format one SSE event. Data must already be sanitized."""
    if isinstance(data, dict):
        payload = json.dumps(data, default=str, separators=(",", ":"))
    else:
        payload = data
    return f"event: {event}\ndata: {payload}\n\n"


def format_sse_comment(text: str = "keepalive") -> str:
    return f": {text}\n\n"


def sanitize_public_error_message(raw: str, *, code: str = "agent_error") -> tuple[str, str]:
    """Return (code, message) safe for SSE error events."""
    text = _THINK_RE.sub("", raw or "")
    text = _STACK_RE.sub("", text)
    text = " ".join(text.split())
    if _SENSITIVE_RE.search(text):
        return code, "Unable to complete the packing request."
    if len(text) > 200:
        text = text[:197] + "..."
    if not text:
        return code, "Unable to complete the packing request."
    # Never echo model internals that look like JSON blobs of thoughts.
    if text.lstrip().startswith("{") and "chain" in text.lower():
        return code, "Unable to complete the packing request."
    return code, text


def packing_response_json(response: Any) -> dict[str, Any]:
    """Serialize PackingResponse for the completed event."""
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    return dict(response)
