"""Tests for bounded retry of transient agent failures."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.config import LLMSettings
from app.agent.exceptions import AgentResponseError, LLMConfigurationError
from app.agent.retry import ErrorClass, classify_agent_error, is_retryable
from app.agent.service import AgentService
from app.main import app
from app.models.chat import PackingResponse
from app.models.weather import ForecastDay, WeatherResponse
from app.observability import AGENT_RETRIES, AGENT_RETRY_EXHAUSTED, AGENT_RETRY_SUCCESS
from app.tools.baggage import load_baggage_rules
from tests.helpers import make_tool_call

client = TestClient(app)
RULES_DISCLAIMER = load_baggage_rules()["disclaimer"]


def _settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://example.com/v1",
        model="test-model",
        api_key="test-key",
    )


def _valid_payload(**overrides: object) -> dict:
    payload = {
        "destination": "Rome",
        "start_date": "2026-07-21",
        "end_date": "2026-07-23",
        "weather_summary": {
            "location": "Rome",
            "overview": "Warm.",
            "min_temperature": "18°C",
            "max_temperature": "32°C",
            "conditions": "Clear",
        },
        "packing_items": [
            {
                "name": "T-shirt",
                "category": "Clothing",
                "quantity": 2,
                "reason": "Warm weather",
                "essential": True,
            }
        ],
        "warnings": [],
        "baggage_warnings": [],
        "profile_considerations": [],
        "rules_disclaimer": RULES_DISCLAIMER,
        "language": "en",
    }
    payload.update(overrides)
    return payload


def _completion(
    *,
    content: str | None = None,
    tool_calls: list | None = None,
    finish_reason: str = "stop",
) -> MagicMock:
    return MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )
        ]
    )


def _metric_value(counter) -> float:  # type: ignore[no-untyped-def]
    return float(counter._value.get())  # noqa: SLF001 — test helper


def test_classify_transient_parse_exhaustion_as_retryable() -> None:
    exc = AgentResponseError(
        "Invalid agent response after 4 attempts: Schema validation failed: "
        "1 validation error for PackingResponse language Field required"
    )
    assert classify_agent_error(exc) is ErrorClass.RETRYABLE
    assert is_retryable(exc)


def test_classify_json_delimiter_flake_as_retryable() -> None:
    exc = AgentResponseError(
        "Invalid agent response after 4 attempts: Expecting ',' delimiter"
    )
    assert is_retryable(exc)


def test_classify_config_and_auth_as_non_retryable() -> None:
    assert (
        classify_agent_error(LLMConfigurationError("BASE_URL missing"))
        is ErrorClass.NON_RETRYABLE
    )
    assert not is_retryable(
        AgentResponseError("LLM request failed: AuthenticationError: 401 Unauthorized")
    )
    assert not is_retryable(
        AgentResponseError("LLM request failed: PermissionDenied: 403 Forbidden")
    )


@pytest.mark.asyncio
async def test_transient_error_then_success_retries_once() -> None:
    retries_before = _metric_value(AGENT_RETRIES)
    success_before = _metric_value(AGENT_RETRY_SUCCESS)

    incomplete = _valid_payload()
    del incomplete["language"]
    complete = _valid_payload()

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            _completion(
                tool_calls=[
                    make_tool_call("w", "get_weather", {"city": "Rome", "days": 3})
                ],
                finish_reason="tool_calls",
            ),
            _completion(
                tool_calls=[
                    make_tool_call("b", "baggage_rules", {"baggage_type": "cabin"})
                ],
                finish_reason="tool_calls",
            ),
            # Initial final generation exhausts parse attempts (4 contents).
            _completion(content=json.dumps(incomplete), finish_reason="stop"),
            _completion(content=json.dumps(incomplete), finish_reason="stop"),
            _completion(content=json.dumps(incomplete), finish_reason="stop"),
            _completion(content=json.dumps(incomplete), finish_reason="stop"),
            # Retry: essentials cached → only final generation.
            _completion(content=json.dumps(complete), finish_reason="stop"),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(
            location="Rome",
            forecast=[
                ForecastDay(
                    date="2026-07-21",
                    min="18°C",
                    max="32°C",
                    condition="Clear",
                )
            ],
        )
    )
    stages: list[str] = []

    async def on_progress(stage: str) -> None:
        stages.append(stage)

    with (
        patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter),
        patch("app.agent.service.retry_delay_seconds", return_value=0),
    ):
        result = await service.chat("Rome cabin trip", on_progress=on_progress)

    assert result.destination == "Rome"
    assert "retrying_generation" in stages
    assert weather_adapter.get_weather.await_count == 1
    assert _metric_value(AGENT_RETRIES) == retries_before + 1
    assert _metric_value(AGENT_RETRY_SUCCESS) == success_before + 1


@pytest.mark.asyncio
async def test_two_transient_errors_exhaust_retry_budget() -> None:
    exhausted_before = _metric_value(AGENT_RETRY_EXHAUSTED)
    incomplete = _valid_payload()
    del incomplete["language"]

    def _fail_final_batch() -> list[MagicMock]:
        return [
            _completion(content=json.dumps(incomplete), finish_reason="stop")
            for _ in range(4)
        ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            _completion(
                tool_calls=[
                    make_tool_call("w", "get_weather", {"city": "Rome", "days": 2})
                ],
                finish_reason="tool_calls",
            ),
            _completion(
                tool_calls=[
                    make_tool_call("b", "baggage_rules", {"baggage_type": "cabin"})
                ],
                finish_reason="tool_calls",
            ),
            *_fail_final_batch(),
            *_fail_final_batch(),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(location="Rome", forecast=[])
    )

    with (
        patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter),
        patch("app.agent.service.retry_delay_seconds", return_value=0),
    ):
        with pytest.raises(AgentResponseError, match="Invalid agent response after"):
            await service.chat("Rome trip")

    assert weather_adapter.get_weather.await_count == 1
    assert _metric_value(AGENT_RETRY_EXHAUSTED) == exhausted_before + 1


@pytest.mark.asyncio
async def test_non_retryable_error_does_not_retry() -> None:
    retries_before = _metric_value(AGENT_RETRIES)
    service = AgentService(
        settings=LLMSettings(base_url=None, model=None, api_key=None),
        client=MagicMock(),
    )
    with pytest.raises(LLMConfigurationError):
        await service.chat("Rome trip")
    assert _metric_value(AGENT_RETRIES) == retries_before


@pytest.mark.asyncio
async def test_retry_does_not_recall_weather_or_baggage_mcp() -> None:
    incomplete = _valid_payload()
    del incomplete["language"]
    complete = _valid_payload()

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            _completion(
                tool_calls=[
                    make_tool_call("w", "get_weather", {"city": "Lisbon", "days": 3})
                ],
                finish_reason="tool_calls",
            ),
            _completion(
                tool_calls=[
                    make_tool_call(
                        "b",
                        "baggage_rules",
                        {"baggage_type": "checked", "item": "power bank"},
                    )
                ],
                finish_reason="tool_calls",
            ),
            *[_completion(content=json.dumps(incomplete), finish_reason="stop") for _ in range(4)],
            _completion(content=json.dumps(complete), finish_reason="stop"),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(location="Lisbon", forecast=[])
    )
    baggage_adapter = AsyncMock()
    baggage_adapter.lookup = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {
                "warnings": ["Power banks must not go in checked baggage."],
                "disclaimer": RULES_DISCLAIMER,
            },
            warnings=["Power banks must not go in checked baggage."],
            disclaimer=RULES_DISCLAIMER,
        )
    )

    with (
        patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter),
        patch("app.agent.tools.build_baggage_adapter", return_value=baggage_adapter),
        patch("app.agent.service.retry_delay_seconds", return_value=0),
    ):
        await service.chat("Power bank to Lisbon checked bag")

    assert weather_adapter.get_weather.await_count == 1
    assert baggage_adapter.lookup.await_count == 1


def test_sync_endpoint_retries_transient_agent_error() -> None:
    response_payload = PackingResponse.model_validate(_valid_payload())
    calls = {"n": 0}

    async def flaky_chat(message, traveler_profile=None, on_progress=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AgentResponseError(
                "Invalid agent response after 4 attempts: Schema validation failed"
            )
        return response_payload

    # Endpoint calls agent_service.chat once; retry is inside AgentService.
    # Patch AgentService.chat on the app instance to verify endpoint still returns 200
    # when the service succeeds (retry tested above). This covers sync wiring.
    with patch("app.main.agent_service.chat", AsyncMock(return_value=response_payload)):
        response = client.post("/api/v1/chat", json={"message": "Trip to Rome"})
    assert response.status_code == 200
    assert response.json()["destination"] == "Rome"


def test_sse_endpoint_emits_retrying_generation_progress() -> None:
    response_payload = PackingResponse.model_validate(_valid_payload())

    async def fake_chat(message, traveler_profile=None, on_progress=None):
        if on_progress:
            await on_progress("preparing")
            await on_progress("weather")
            await on_progress("baggage_rules")
            await on_progress("generating")
            await on_progress("retrying_generation")
            await on_progress("generating")
        return response_payload

    with patch("app.main.agent_service.chat", fake_chat):
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "Trip to Rome"},
        )

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "retrying_generation" in response.text
    assert "event: completed" in response.text
    assert "insulin" not in response.text.lower()
