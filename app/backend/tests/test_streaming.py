"""Tests for POST /api/v1/chat/stream SSE protocol."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.exceptions import AgentResponseError, LLMConfigurationError
from app.agent.progress import ProgressCallback
from app.main import HEARTBEAT_INTERVAL_SECONDS, app
from app.models.chat import PackingResponse
from app.streaming import format_sse, sanitize_public_error_message


def _sample_packing() -> PackingResponse:
    return PackingResponse.model_validate(
        {
            "destination": "Rome",
            "start_date": "2026-07-21",
            "end_date": "2026-07-24",
            "weather_summary": {
                "location": "Rome",
                "overview": "Warm and sunny.",
            },
            "packing_items": [
                {
                    "name": "T-shirt",
                    "category": "Clothing",
                    "quantity": 3,
                    "reason": "Warm weather",
                    "essential": True,
                }
            ],
            "warnings": [],
            "baggage_warnings": ["Cabin liquids limited to 100 ml demo rule."],
            "profile_considerations": [],
            "rules_disclaimer": "DEMONSTRATION RULES ONLY.",
            "language": "en",
        }
    )


def _parse_sse(body: str) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    blocks = body.split("\n\n")
    for block in blocks:
        if not block.strip() or block.strip().startswith(":"):
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if data_lines:
            raw = "\n".join(data_lines)
            try:
                events.append((event_name, json.loads(raw)))
            except json.JSONDecodeError:
                events.append((event_name, raw))
    return events


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_stream_content_type_and_started_first(client: TestClient) -> None:
    async def fake_chat(message, traveler_profile=None, on_progress=None):
        if on_progress:
            await on_progress("weather")
        return _sample_packing()

    with patch("app.main.agent_service.chat", side_effect=fake_chat):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome with cabin bag"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert response.headers.get("cache-control") == "no-cache"
            assert response.headers.get("x-accel-buffering") == "no"
            body = "".join(response.iter_text())

    events = _parse_sse(body)
    assert events[0][0] == "started"
    assert events[0][1]["status"] == "processing"
    assert "trace_id" in events[0][1]
    assert any(name == "completed" for name, _ in events)
    completed = next(data for name, data in events if name == "completed")
    assert completed["destination"] == "Rome"
    assert "think" not in body.lower()
    assert "insulin" not in body.lower()


def test_stream_progress_stages(client: TestClient) -> None:
    async def fake_chat(message, traveler_profile=None, on_progress=None):
        if on_progress:
            await on_progress("weather")
            await on_progress("baggage_rules")
            await on_progress("generating")
        return _sample_packing()

    with patch("app.main.agent_service.chat", side_effect=fake_chat):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome"},
        ) as response:
            body = "".join(response.iter_text())

    stages = [data["stage"] for name, data in _parse_sse(body) if name == "progress"]
    assert stages == ["weather", "baggage_rules", "generating"]


def test_stream_heartbeat_during_slow_agent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.HEARTBEAT_INTERVAL_SECONDS", 0.05)

    async def slow_chat(message, traveler_profile=None, on_progress=None):
        await asyncio.sleep(0.18)
        return _sample_packing()

    with patch("app.main.agent_service.chat", side_effect=slow_chat):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome"},
        ) as response:
            body = "".join(response.iter_text())

    events = _parse_sse(body)
    heartbeats = [e for e in events if e[0] == "heartbeat"]
    assert len(heartbeats) >= 2
    assert any(e[0] == "completed" for e in events)
    assert ": keepalive" in body


def test_stream_error_sanitized(client: TestClient) -> None:
    async def failing_chat(message, traveler_profile=None, on_progress=None):
        raise AgentResponseError(
            "Invalid agent response after 3 attempts: <think>secret chain</think> insulin note"
        )

    with patch("app.main.agent_service.chat", side_effect=failing_chat):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome"},
        ) as response:
            body = "".join(response.iter_text())

    events = _parse_sse(body)
    errors = [data for name, data in events if name == "error"]
    assert len(errors) == 1
    assert errors[0]["code"] == "agent_error"
    assert "trace_id" in errors[0]
    assert "think" not in body.lower()
    assert "insulin" not in body.lower()
    assert "Traceback" not in body


def test_stream_llm_config_error(client: TestClient) -> None:
    async def failing_chat(message, traveler_profile=None, on_progress=None):
        raise LLMConfigurationError("BASE_URL missing")

    with patch("app.main.agent_service.chat", side_effect=failing_chat):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome"},
        ) as response:
            body = "".join(response.iter_text())

    errors = [data for name, data in _parse_sse(body) if name == "error"]
    assert errors[0]["code"] == "llm_not_configured"


def test_stream_simulated_over_60s_with_heartbeats(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Heartbeats keep the stream alive for a long agent run (clock accelerated)."""
    monkeypatch.setattr("app.main.HEARTBEAT_INTERVAL_SECONDS", 0.02)

    async def long_chat(message, traveler_profile=None, on_progress=None):
        # ~70 heartbeat slots at 0.02s would be 1.4s wall; we only need many frames.
        await asyncio.sleep(0.25)
        return _sample_packing()

    with patch("app.main.agent_service.chat", side_effect=long_chat):
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome cabin bag"},
        ) as response:
            body = "".join(response.iter_text())

    events = _parse_sse(body)
    heartbeats = [e for e in events if e[0] == "heartbeat"]
    assert len(heartbeats) >= 5
    assert events[0][0] == "started"
    assert any(e[0] == "completed" for e in events)


def test_sync_chat_still_works(client: TestClient) -> None:
    with patch(
        "app.main.agent_service.chat",
        AsyncMock(return_value=_sample_packing()),
    ):
        response = client.post("/api/v1/chat", json={"message": "Trip to Rome"})
    assert response.status_code == 200
    assert response.json()["destination"] == "Rome"


def test_sanitize_public_error_message_strips_think_and_sensitive() -> None:
    code, msg = sanitize_public_error_message(
        "boom <think>hidden</think> Requires insulin refrigeration Traceback (most recent call last): x"
    )
    assert code == "agent_error"
    assert "think" not in msg.lower()
    assert "insulin" not in msg.lower()
    assert "Traceback" not in msg


def test_format_sse_shape() -> None:
    frame = format_sse("heartbeat", {"status": "processing"})
    assert frame.startswith("event: heartbeat\n")
    assert "data: {" in frame
    assert frame.endswith("\n\n")
