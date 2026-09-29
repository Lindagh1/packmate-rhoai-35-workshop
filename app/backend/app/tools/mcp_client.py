"""Streamable HTTP MCP client used by Packmate in PACKMATE_TOOL_MODE=mcp."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.observability import span

logger = logging.getLogger(__name__)

# Keys that must never appear in MCP tool arguments.
_FORBIDDEN_ARGUMENT_KEYS = {
    "medical_or_accessibility_notes",
    "medical_notes",
    "sensitive_notes",
    "notes",
    "share_sensitive_notes_with_model",
}


class MCPClientError(Exception):
    """Sanitized MCP client failure (no upstream payloads with secrets)."""


def assert_safe_mcp_arguments(arguments: dict[str, Any]) -> None:
    """Raise if sensitive keys are present in outbound MCP arguments."""
    for key in arguments:
        if str(key).lower() in _FORBIDDEN_ARGUMENT_KEYS:
            raise MCPClientError(
                f"Refusing to send sensitive key to MCP server: {key}"
            )
    blob = json.dumps(arguments, default=str)
    if "medical_or_accessibility_notes" in blob:
        raise MCPClientError("Refusing to send sensitive content to MCP server")


async def call_mcp_tool(
    url: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout_seconds: float = 10.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Call a remote MCP tool and return a JSON-serializable dict."""
    assert_safe_mcp_arguments(arguments)

    last_error: Exception | None = None
    attempts = max_retries + 1

    for attempt in range(1, attempts + 1):
        try:
            with span(
                "mcp.call_tool",
                {
                    "mcp.tool": tool_name,
                    "mcp.attempt": attempt,
                    "mcp.url_host": url.split("/")[2] if "://" in url else "unknown",
                },
            ):
                return await asyncio.wait_for(
                    _call_once(url, tool_name, arguments),
                    timeout=timeout_seconds,
                )
        except TimeoutError as exc:
            last_error = exc
            logger.warning("MCP tool %s timed out (attempt %s/%s)", tool_name, attempt, attempts)
        except Exception as exc:  # noqa: BLE001 — sanitized below
            last_error = exc
            logger.warning(
                "MCP tool %s failed (attempt %s/%s): %s",
                tool_name,
                attempt,
                attempts,
                type(exc).__name__,
            )
        except BaseExceptionGroup as exc:
            # MCP streamable HTTP can raise ExceptionGroup; it is not an Exception subclass.
            last_error = exc
            logger.warning(
                "MCP tool %s failed (attempt %s/%s): %s",
                tool_name,
                attempt,
                attempts,
                type(exc).__name__,
            )
        if attempt < attempts:
            await asyncio.sleep(min(0.25 * attempt, 1.0))

    raise MCPClientError(
        f"MCP tool '{tool_name}' unavailable after {attempts} attempt(s)"
    ) from last_error


async def _call_once(url: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with streamable_http_client(url) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return _normalize_tool_result(result)


def _normalize_tool_result(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False):
        raise MCPClientError("MCP tool returned an error result")

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    contents = getattr(result, "content", None) or []
    texts: list[str] = []
    for item in contents:
        text = getattr(item, "text", None)
        if text:
            texts.append(text)
    if not texts:
        return {}
    if len(texts) == 1:
        try:
            parsed = json.loads(texts[0])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"text": texts[0]}
    return {"texts": texts}
