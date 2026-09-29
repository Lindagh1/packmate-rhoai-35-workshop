import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.config import LLMSettings
from app.agent.exceptions import AgentResponseError, ParseError
from app.agent.parser import parse_packing_response
from app.agent.service import AgentService
from app.main import app
from app.models.chat import PackingResponse
from app.models.profile import TravelerProfile
from app.tools.baggage import BAGGAGE_RULES_PATH, load_baggage_rules, lookup_baggage_rules
from tests.helpers import make_tool_call

client = TestClient(app)

RULES_DISCLAIMER = load_baggage_rules()["disclaimer"]


@pytest.fixture(autouse=True)
def clear_rules_cache() -> None:
    load_baggage_rules.cache_clear()
    yield
    load_baggage_rules.cache_clear()


def test_baggage_rules_file_loads_from_package_path() -> None:
    expected = Path(__file__).resolve().parents[1] / "app" / "data" / "baggage_rules.json"

    assert BAGGAGE_RULES_PATH == expected
    assert load_baggage_rules()["version"] == "1.0.0-demo"


def test_liquid_over_100ml_in_cabin_returns_warning() -> None:
    result = lookup_baggage_rules(
        baggage_type="cabin",
        item="shampoo 200ml",
        category="liquids",
    )

    assert "liquids_over_100ml_cabin" in result.matched_rule_ids
    assert any("100 ml" in warning for warning in result.warnings)


def test_external_battery_returns_warning() -> None:
    result = lookup_baggage_rules(
        baggage_type="cabin",
        item="power bank",
        category="electronics",
    )

    assert "external_batteries" in result.matched_rule_ids
    assert any("power banks" in warning.lower() for warning in result.warnings)


def test_sharp_object_returns_warning() -> None:
    result = lookup_baggage_rules(
        baggage_type="cabin",
        item="kitchen knife",
        category="sharp_objects",
    )

    assert "sharp_objects" in result.matched_rule_ids
    assert any("sharp objects" in warning.lower() for warning in result.warnings)


def test_include_general_rules_adds_weight_and_dimension_limits() -> None:
    result = lookup_baggage_rules(
        baggage_type="cabin",
        include_general_rules=True,
    )

    assert result.general_rules
    assert any("8 kg" in rule for rule in result.general_rules)


def test_rules_include_airline_disclaimer() -> None:
    result = lookup_baggage_rules(baggage_type="cabin")

    assert "airline" in result.disclaimer.lower()


@pytest.mark.asyncio
async def test_agent_merges_deterministic_baggage_warnings() -> None:
    llm_payload = {
        **{
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
            "language": "fr",
        }
    }
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
                MagicMock(
                    choices=[
                        MagicMock(
                            message=MagicMock(
                                content=None,
                                tool_calls=[
                                    make_tool_call(
                                        "call_baggage",
                                        "baggage_rules",
                                        {
                                            "baggage_type": "cabin",
                                            "item": "power bank",
                                        },
                                    )
                                ],
                            )
                        )
                    ]
                ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content=json.dumps(llm_payload), tool_calls=None)
                    )
                ]
            ),
        ]
    )

    service = AgentService(
        settings=LLMSettings(
            base_url="https://example.com/v1",
            model="test-model",
            api_key="test-key",
        ),
        client=mock_client,
    )

    result = await service.chat("Je pars à Rome avec une batterie externe")

    assert any("power banks" in warning.lower() for warning in result.baggage_warnings)
    assert result.rules_disclaimer == RULES_DISCLAIMER


@pytest.mark.asyncio
async def test_agent_processes_one_tool_when_model_emits_multiple() -> None:
    """llama-32 gateway rejects multi-tool history; only the first priority tool is kept."""
    tool_calls = [
        make_tool_call("call_weather", "get_weather", {"city": "Rome", "days": 3}),
        make_tool_call(
            "call_baggage",
            "baggage_rules",
            {"baggage_type": "cabin", "item": "knife"},
        ),
        make_tool_call("call_profile", "traveler_profile", {}),
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content=None, tool_calls=tool_calls),
                        finish_reason="tool_calls",
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=None,
                            tool_calls=[
                                make_tool_call(
                                    "call_baggage_2",
                                    "baggage_rules",
                                    {"baggage_type": "cabin", "item": "knife"},
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(_valid_response_payload()),
                            tool_calls=None,
                        ),
                        finish_reason="stop",
                    )
                ]
            ),
        ]
    )

    profile = TravelerProfile(
        trip_type="business",
        baggage_type="cabin",
        activities=["meetings"],
        clothing_preferences=["formal"],
    )
    service = AgentService(
        settings=LLMSettings(
            base_url="https://example.com/v1",
            model="test-model",
            api_key="test-key",
        ),
        client=mock_client,
    )

    weather_adapter = AsyncMock()
    weather_adapter.get_weather = AsyncMock(
        return_value=MagicMock(model_dump=lambda: {"location": "Rome"})
    )
    with patch("app.agent.tools.build_weather_adapter", return_value=weather_adapter):
        result = await service.chat("Je pars à Rome", traveler_profile=profile)

    assert result.destination == "Rome"
    assert mock_client.chat.completions.create.call_count == 3
    # messages list is mutated in place; assert every assistant tool turn stays single-call.
    final_messages = mock_client.chat.completions.create.call_args_list[-1].kwargs["messages"]
    assistant_tool_turns = [
        m for m in final_messages if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    assert assistant_tool_turns
    assert all(len(m["tool_calls"]) == 1 for m in assistant_tool_turns)
    assert assistant_tool_turns[0]["tool_calls"][0]["function"]["name"] == "get_weather"


def test_packing_response_accepts_iso_dates() -> None:
    response = PackingResponse.model_validate(_valid_response_payload())

    assert response.start_date == date(2026, 7, 21)
    assert response.end_date == date(2026, 7, 23)


def test_packing_response_rejects_end_date_before_start_date() -> None:
    payload = _valid_response_payload()
    payload["start_date"] = "2026-07-23"
    payload["end_date"] = "2026-07-21"

    with pytest.raises(ValidationError, match="end_date cannot be earlier than start_date"):
        PackingResponse.model_validate(payload)


def test_parser_rejects_invalid_date_order() -> None:
    payload = _valid_response_payload()
    payload["start_date"] = "2026-07-23"
    payload["end_date"] = "2026-07-21"

    with pytest.raises(ParseError, match="Schema validation failed"):
        parse_packing_response(json.dumps(payload))


def test_medical_notes_not_leaked_in_parse_error() -> None:
    payload = _valid_response_payload()
    payload["start_date"] = "2026-07-23"
    payload["end_date"] = "2026-07-21"

    with pytest.raises(ParseError) as exc_info:
        parse_packing_response(json.dumps(payload))

    assert "insulin" not in str(exc_info.value).lower()


def test_medical_notes_not_logged_during_tool_execution(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from app.agent.context import ToolContext
    from app.agent.tools import execute_tool

    caplog.set_level(logging.INFO)
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
    )
    context = ToolContext(traveler_profile=profile)

    import asyncio

    asyncio.run(execute_tool("traveler_profile", "{}", context))

    log_text = caplog.text.lower()
    assert "insulin" not in log_text
    assert "requires insulin" not in log_text


@pytest.mark.asyncio
async def test_agent_response_error_does_not_leak_medical_notes() -> None:
    service = AgentService(
        settings=LLMSettings(
            base_url="https://example.com/v1",
            model="test-model",
            api_key="test-key",
        ),
        client=MagicMock(),
    )
    profile = TravelerProfile(
        trip_type="leisure",
        baggage_type="cabin",
        activities=["walking"],
        clothing_preferences=["casual"],
        medical_or_accessibility_notes=["Requires insulin refrigeration"],
    )

    with patch.object(
        service,
        "_parse_with_retries",
        AsyncMock(
            side_effect=AgentResponseError(
                "Invalid agent response after 3 attempts: Schema validation failed: end_date invalid"
            )
        ),
    ), patch.object(
        service,
        "_llm_create",
        AsyncMock(
            return_value=MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"language":"fr"}',
                            tool_calls=None,
                        )
                    )
                ]
            )
        ),
    ):
        with pytest.raises(AgentResponseError) as exc_info:
            await service.chat("Je pars à Rome", traveler_profile=profile)

    assert "insulin" not in str(exc_info.value).lower()


def test_chat_endpoint_accepts_traveler_profile() -> None:
    mock_response = PackingResponse.model_validate(_valid_response_payload())

    with patch("app.main.agent_service.chat", AsyncMock(return_value=mock_response)) as mock_chat:
        response = client.post(
            "/api/v1/chat",
            json={
                "message": "Je pars à Rome",
                "traveler_profile": {
                    "trip_type": "business",
                    "baggage_type": "cabin",
                    "activities": ["meetings"],
                    "clothing_preferences": ["formal"],
                },
            },
        )

    assert response.status_code == 200
    mock_chat.assert_awaited_once()
    assert mock_chat.await_args.args[1].trip_type == "business"


def _valid_response_payload() -> dict:
    return {
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
                "name": "Chemise",
                "category": "Clothing",
                "quantity": 2,
                "reason": "Business",
                "essential": True,
            }
        ],
        "warnings": [],
        "baggage_warnings": [],
        "profile_considerations": ["Business attire recommended."],
        "rules_disclaimer": RULES_DISCLAIMER,
        "language": "fr",
    }
