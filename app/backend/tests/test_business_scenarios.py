"""Regression tests for the four remaining business-failure scenarios.

All LLM/MCP interactions are mocked — no real model calls.
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.config import LLMSettings
from app.agent.enrichment import collect_packing_item_warnings, enrich_packing_response
from app.agent.parser import parse_packing_response
from app.agent.service import AgentService
from app.main import app
from app.models.chat import PackingItem, PackingResponse, WeatherSummary
from app.models.profile import TravelerProfile
from app.models.weather import ForecastDay, WeatherResponse
from app.tools.baggage import load_baggage_rules
from tests.helpers import make_tool_call

client = TestClient(app)
RULES_DISCLAIMER = load_baggage_rules()["disclaimer"]


def _valid_payload(**overrides: object) -> dict:
    payload = {
        "destination": "Rome",
        "start_date": "2026-07-21",
        "end_date": "2026-07-23",
        "weather_summary": {
            "location": "Rome",
            "overview": "Warm and clear.",
            "min_temperature": "18°C",
            "max_temperature": "32°C",
            "conditions": "Clear",
            "daily_forecast": [],
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
        "baggage_warnings": [],
        "profile_considerations": [],
        "rules_disclaimer": RULES_DISCLAIMER,
        "language": "en",
    }
    payload.update(overrides)
    return payload


def _settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://example.com/v1",
        model="test-model",
        api_key="test-key",
    )


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


def _weather() -> WeatherResponse:
    return WeatherResponse(
        location="Innsbruck",
        forecast=[
            ForecastDay(
                date="2026-09-10",
                min="8°C",
                max="18°C",
                condition="Partly cloudy",
            )
        ],
    )


@pytest.mark.asyncio
async def test_hiking_dolomites_single_tool_then_final_json() -> None:
    """Hiking failed when the model emitted 3 tool calls and poisoned history."""
    multi = [
        make_tool_call("w", "get_weather", {"city": "Innsbruck", "days": 7}),
        make_tool_call("b", "baggage_rules", {"baggage_type": "checked"}),
        make_tool_call("p", "traveler_profile", {}),
    ]
    final = _valid_payload(
        destination="Innsbruck",
        start_date="2026-09-10",
        end_date="2026-09-17",
        weather_summary={
            "location": "Innsbruck",
            "overview": "Cool alpine weather.",
            "min_temperature": "8°C",
            "max_temperature": "18°C",
            "conditions": "Partly cloudy",
        },
        packing_items=[
            {
                "name": "Hiking boots",
                "category": "Footwear",
                "quantity": 1,
                "reason": "Mountain trails",
                "essential": True,
            }
        ],
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            _completion(tool_calls=multi, finish_reason="tool_calls"),
            _completion(
                tool_calls=[
                    make_tool_call("b2", "baggage_rules", {"baggage_type": "checked"})
                ],
                finish_reason="tool_calls",
            ),
            _completion(content=json.dumps(final), finish_reason="stop"),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(return_value=_weather())

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat(
            "Week-long hiking trip in the Dolomites in September with checked bag."
        )

    assert result.destination == "Innsbruck"
    assert any("boot" in item.name.lower() for item in result.packing_items)
    # Final generation uses raised token budget.
    final_kwargs = mock_client.chat.completions.create.call_args_list[2].kwargs
    assert final_kwargs["max_tokens"] == AgentService.MAX_FINAL_COMPLETION_TOKENS
    assert "tools" not in final_kwargs


@pytest.mark.asyncio
async def test_powerbank_checked_recovers_truncated_json_and_warnings() -> None:
    """Powerbank failed on finish_reason=length then missing weather_summary."""
    incomplete = {
        "destination": "Lisbon",
        "start_date": "2026-07-20",
        "end_date": "2026-07-22",
        "packing_items": [
            {
                "name": "Power bank 20000 mAh",
                "category": "Electronics",
                "quantity": 1,
                "reason": "Device charging",
                "essential": True,
            }
        ],
        "warnings": [],
        "baggage_warnings": [],
        "profile_considerations": [],
        "rules_disclaimer": RULES_DISCLAIMER,
        "language": "en",
        # weather_summary intentionally omitted — recoverable from tool context
    }
    complete = _valid_payload(
        destination="Lisbon",
        packing_items=incomplete["packing_items"],
        weather_summary={
            "location": "Lisbon",
            "overview": "Mild.",
            "min_temperature": "18°C",
            "max_temperature": "28°C",
            "conditions": "Clear",
        },
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
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
            _completion(
                tool_calls=[
                    make_tool_call("w", "get_weather", {"city": "Lisbon", "days": 3})
                ],
                finish_reason="tool_calls",
            ),
            _completion(
                content=json.dumps(incomplete),
                finish_reason="length",
            ),
            # Truncation retry inside _generate_final_json
            _completion(content=json.dumps(complete), finish_reason="stop"),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(
            location="Lisbon",
            forecast=[
                ForecastDay(
                    date="2026-07-20",
                    min="18°C",
                    max="28°C",
                    condition="Clear",
                )
            ],
        )
    )

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat(
            "Can I pack a 20000 mAh power bank in checked luggage to Lisbon?"
        )

    assert result.destination == "Lisbon"
    assert result.weather_summary.location == "Lisbon"
    assert any("power" in w.lower() for w in result.baggage_warnings)


@pytest.mark.asyncio
async def test_liquid_cabin_parses_json_with_missing_commas() -> None:
    """Liquid failed on Invalid JSON: Expecting ',' delimiter."""
    broken = (
        '{"destination": "Barcelona", "start_date": "2026-07-20", '
        '"end_date": "2026-07-24", '
        '"weather_summary": {"location": "Barcelona", "overview": "Warm."}, '
        '"packing_items": [{"name": "Travel shampoo", "category": "Toiletries", '
        '"quantity": 1, "reason": "Hygiene", "essential": true}], '
        '"warnings": [] '
        '"baggage_warnings": [], '
        '"profile_considerations": [], '
        '"rules_disclaimer": '
        + json.dumps(RULES_DISCLAIMER)
        + ', "language": "en"}'
    )
    # Ensure the broken sample is invalid before repair.
    with pytest.raises(Exception):
        json.loads(broken)

    parsed = parse_packing_response(broken)
    assert parsed.destination == "Barcelona"

    enriched = enrich_packing_response(
        response=parsed,
        profile=TravelerProfile(trip_type="leisure", baggage_type="cabin"),
        collected_baggage_warnings=[],
        rules_disclaimer=RULES_DISCLAIMER,
    )
    assert any("100" in w for w in enriched.baggage_warnings) or any(
        "liquid" in w.lower() for w in enriched.baggage_warnings
    )


@pytest.mark.asyncio
async def test_oslo_cabin_winter_forces_final_after_essentials() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            _completion(
                tool_calls=[
                    make_tool_call("w", "get_weather", {"city": "Oslo", "days": 3})
                ],
                finish_reason="tool_calls",
            ),
            _completion(
                tool_calls=[
                    make_tool_call("b", "baggage_rules", {"baggage_type": "cabin"})
                ],
                finish_reason="tool_calls",
            ),
            _completion(
                content=json.dumps(
                    _valid_payload(
                        destination="Oslo",
                        start_date="2026-02-14",
                        end_date="2026-02-16",
                        weather_summary={
                            "location": "Oslo",
                            "overview": "Cold with snow.",
                            "min_temperature": "-8°C",
                            "max_temperature": "-2°C",
                            "conditions": "Snow",
                        },
                        packing_items=[
                            {
                                "name": "Winter coat",
                                "category": "Clothing",
                                "quantity": 1,
                                "reason": "Snow",
                                "essential": True,
                            }
                        ],
                    )
                ),
                finish_reason="stop",
            ),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(
            location="Oslo",
            forecast=[
                ForecastDay(
                    date="2026-02-14",
                    min="-8°C",
                    max="-2°C",
                    condition="Snow",
                )
            ],
        )
    )

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat(
            "Weekend in Oslo in February, cabin bag only, expect snow."
        )

    assert result.destination == "Oslo"
    assert "snow" in result.weather_summary.overview.lower() or result.weather_summary.conditions
    # After essentials, third call must be tool-free final generation.
    final_call = mock_client.chat.completions.create.call_args_list[2]
    assert "tools" not in final_call.kwargs
    nudge = final_call.kwargs["messages"][-1]["content"]
    assert "Do not call tools" in nudge or "valid JSON" in nudge


@pytest.mark.asyncio
async def test_duplicate_identical_tool_call_uses_cache() -> None:
    weather_call = make_tool_call("w1", "get_weather", {"city": "Rome", "days": 3})
    weather_call_dup = make_tool_call("w2", "get_weather", {"city": "Rome", "days": 3})
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            _completion(tool_calls=[weather_call], finish_reason="tool_calls"),
            _completion(tool_calls=[weather_call_dup], finish_reason="tool_calls"),
            _completion(
                tool_calls=[
                    make_tool_call("b", "baggage_rules", {"baggage_type": "cabin"})
                ],
                finish_reason="tool_calls",
            ),
            _completion(content=json.dumps(_valid_payload()), finish_reason="stop"),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(location="Rome", forecast=[])
    )

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        await service.chat("Trip to Rome with cabin bag")

    assert weather_adapter.get_weather.await_count == 1


@pytest.mark.asyncio
async def test_recover_missing_weather_summary_from_tool_context() -> None:
    payload = _valid_payload()
    del payload["weather_summary"]
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
            _completion(content=json.dumps(payload), finish_reason="stop"),
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

    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat("Rome cabin trip")

    assert result.weather_summary.location == "Rome"


def test_parser_repairs_trailing_comma_and_prose_wrapper() -> None:
    wrapped = (
        "Here is your packing list:\n"
        + json.dumps(_valid_payload()).replace(
            '"language": "en"',
            '"language": "en",',
        )
        + "\nThanks!"
    )
    # trailing comma before closing brace in language field area — rebuild broken sample
    broken = (
        'Prefix text {"destination": "Rome", "start_date": "2026-07-21", '
        '"end_date": "2026-07-23", '
        '"weather_summary": {"location": "Rome", "overview": "Warm."}, '
        '"packing_items": [], "warnings": [], "baggage_warnings": [], '
        '"profile_considerations": [], '
        '"rules_disclaimer": '
        + json.dumps(RULES_DISCLAIMER)
        + ', "language": "en",}'
    )
    result = parse_packing_response(broken)
    assert result.destination == "Rome"
    assert "Rome" in wrapped


def test_deterministic_baggage_warnings_for_powerbank_and_liquid() -> None:
    items = [
        PackingItem(
            name="Power bank 20000 mAh",
            category="Electronics",
            quantity=1,
            reason="Charge",
            essential=True,
        ),
        PackingItem(
            name="250 ml shampoo",
            category="Toiletries",
            quantity=1,
            reason="Hygiene",
            essential=True,
        ),
    ]
    checked = collect_packing_item_warnings(items, "checked")
    cabin = collect_packing_item_warnings(items, "cabin")
    assert any("power" in w.lower() for w in checked)
    assert any("100" in w or "liquid" in w.lower() for w in cabin)

    response = PackingResponse(
        destination="Lisbon",
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 22),
        weather_summary=WeatherSummary(location="Lisbon", overview="Mild."),
        packing_items=items,
        warnings=[],
        baggage_warnings=[],
        profile_considerations=[],
        rules_disclaimer="ignored",
        language="en",
    )
    enriched = enrich_packing_response(
        response=response,
        profile=TravelerProfile(trip_type="leisure", baggage_type="checked"),
        collected_baggage_warnings=[],
        rules_disclaimer=RULES_DISCLAIMER,
    )
    assert enriched.rules_disclaimer == RULES_DISCLAIMER
    assert enriched.baggage_warnings


def test_parser_repairs_adjacent_objects_and_rejects_tool_shaped_json() -> None:
    from app.agent.exceptions import ParseError
    from app.agent.parser import parse_packing_response

    disclaimer = json.dumps(RULES_DISCLAIMER)
    adjacent = (
        '{"destination":"Rome","start_date":"2026-07-21","end_date":"2026-07-23"'
        ',"weather_summary":{"location":"Rome","overview":"Warm."}'
        ',"packing_items":[{"name":"Shirt","category":"Clothing","quantity":1,'
        '"reason":"Day wear","essential":true}]'
        ',"warnings":[],"baggage_warnings":[],"profile_considerations":[],'
        '"rules_disclaimer":'
        + disclaimer
        + ',"language":"en"}'
        '{"name":"baggage_rules","warnings":[]}'
    )
    broken = (
        '{"destination": "Rome", "start_date": "2026-07-21", '
        '"end_date": "2026-07-23", '
        '"weather_summary": {"location": "Rome", "overview": "Warm."}, '
        '"packing_items": [{"name": "Shirt", "category": "Clothing", '
        '"quantity": 1, "reason": "Day wear", "essential": true}] '
        '"warnings": [], "baggage_warnings": [], "profile_considerations": [], '
        '"rules_disclaimer": '
        + disclaimer
        + ', "language": "en"}'
    )
    assert parse_packing_response(broken).destination == "Rome"
    assert parse_packing_response(adjacent).destination == "Rome"

    with pytest.raises(ParseError, match="tool-shaped"):
        parse_packing_response(
            '{"name":"baggage_rules","warnings":["x"],"disclaimer":"demo"}'
        )


@pytest.mark.asyncio
async def test_empty_packing_items_triggers_parse_retry() -> None:
    empty = _valid_payload(packing_items=[])
    filled = _valid_payload()
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
            _completion(content=json.dumps(empty), finish_reason="stop"),
            _completion(content=json.dumps(filled), finish_reason="stop"),
        ]
    )
    service = AgentService(settings=_settings(), client=mock_client)
    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=WeatherResponse(location="Rome", forecast=[])
    )
    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat("Rome trip")
    assert len(result.packing_items) >= 1
    assert mock_client.chat.completions.create.call_count == 4


def test_parser_uses_json_repair_for_unescaped_quotes() -> None:
    """Models sometimes emit unescaped quotes inside string values."""
    from app.agent.parser import parse_packing_response

    broken = (
        '{"destination": "Lisbon", "start_date": "2026-07-20", '
        '"end_date": "2026-07-22", '
        '"weather_summary": {"location": "Lisbon", "overview": "Mild "sunny" day."}, '
        '"packing_items": [{"name": "Power bank", "category": "Electronics", '
        '"quantity": 1, "reason": "Keep devices charged", "essential": true}], '
        '"warnings": [], "baggage_warnings": [], "profile_considerations": [], '
        '"rules_disclaimer": '
        + json.dumps(RULES_DISCLAIMER)
        + ', "language": "en"}'
    )
    result = parse_packing_response(broken)
    assert result.destination == "Lisbon"
    assert result.packing_items[0].name == "Power bank"

    mock_response = PackingResponse.model_validate(_valid_payload())

    with patch("app.main.agent_service.chat", AsyncMock(return_value=mock_response)):
        sync = client.post("/api/v1/chat", json={"message": "Trip to Rome"})
        assert sync.status_code == 200
        assert sync.json()["destination"] == "Rome"

        stream = client.post("/api/v1/chat/stream", json={"message": "Trip to Rome"})
        assert stream.status_code == 200
        body = stream.text
        assert "event: started" in body
        assert "event: completed" in body
        assert "destination" in body
