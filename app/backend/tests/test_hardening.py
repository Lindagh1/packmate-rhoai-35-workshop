import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.config import LLMSettings
from app.agent.context import ToolContext
from app.agent.enrichment import (
    collect_packing_item_warnings,
    collect_profile_baggage_warnings,
    enrich_packing_response,
    merge_stable_unique,
)
from app.agent.exceptions import AgentResponseError
from app.agent.prompts import build_system_prompt
from app.agent.service import AgentService
from app.agent.tools import execute_tool
from app.models.chat import PackingItem, PackingResponse, WeatherSummary
from app.models.profile import TravelerProfile
from app.tools.baggage import load_baggage_rules
from app.tools.traveler_profile import lookup_traveler_profile
from tests.helpers import make_tool_call

RULES_DISCLAIMER = load_baggage_rules()["disclaimer"]


@pytest.fixture(autouse=True)
def clear_rules_cache() -> None:
    load_baggage_rules.cache_clear()
    yield
    load_baggage_rules.cache_clear()


def _profile_with_notes(**overrides: object) -> TravelerProfile:
    defaults = {
        "trip_type": "leisure",
        "baggage_type": "cabin",
        "activities": ["walking"],
        "clothing_preferences": ["casual"],
        "medical_or_accessibility_notes": ["Requires insulin refrigeration"],
    }
    defaults.update(overrides)
    return TravelerProfile(**defaults)


def _valid_response(**overrides: object) -> PackingResponse:
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
                "name": "Chemise",
                "category": "Clothing",
                "quantity": 2,
                "reason": "Business",
                "essential": True,
            }
        ],
        "warnings": [],
        "baggage_warnings": [],
        "profile_considerations": [],
        "rules_disclaimer": RULES_DISCLAIMER,
        "language": "fr",
    }
    payload.update(overrides)
    return PackingResponse.model_validate(payload)


def test_system_prompt_excludes_medical_notes() -> None:
    prompt = build_system_prompt()

    assert "medical_or_accessibility_notes" not in prompt
    assert "medical_planning_required" in prompt


def test_traveler_profile_tool_result_excludes_notes_by_default() -> None:
    result = lookup_traveler_profile(_profile_with_notes())

    assert "medical_or_accessibility_notes" not in result
    assert "insulin" not in json.dumps(result)


def test_traveler_profile_tool_result_includes_notes_when_shared() -> None:
    profile = _profile_with_notes(share_sensitive_notes_with_model=True)

    result = lookup_traveler_profile(profile)

    assert result["sensitive_notes_shared_with_model"] is True
    assert result["medical_or_accessibility_notes"] == ["Requires insulin refrigeration"]


def test_medical_notes_not_logged_during_tool_execution(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    profile = _profile_with_notes(share_sensitive_notes_with_model=True)
    context = ToolContext(traveler_profile=profile)

    import asyncio

    asyncio.run(execute_tool("traveler_profile", "{}", context))

    assert "insulin" not in caplog.text.lower()


def test_medical_notes_not_leaked_in_agent_response_error() -> None:
    service = AgentService(
        settings=LLMSettings(
            base_url="https://example.com/v1",
            model="test-model",
            api_key="test-key",
        ),
        client=MagicMock(),
    )
    profile = _profile_with_notes()

    with patch.object(
        service,
        "_parse_with_retries",
        AsyncMock(side_effect=AgentResponseError("Invalid agent response after 3 attempts")),
    ):
        with pytest.raises(AgentResponseError) as exc_info:
            import asyncio

            asyncio.run(service.chat("Je pars à Rome", traveler_profile=profile))

    assert "insulin" not in str(exc_info.value).lower()


def test_general_baggage_rules_applied_without_llm_tool_call() -> None:
    profile = TravelerProfile(
        trip_type="business",
        baggage_type="cabin",
        activities=["meetings"],
        clothing_preferences=["formal"],
    )
    context = ToolContext(traveler_profile=profile)

    assert context.collected_baggage_warnings
    assert any("8 kg" in warning or "cabin baggage" in warning.lower() for warning in context.collected_baggage_warnings)


@pytest.mark.asyncio
async def test_general_baggage_rules_applied_in_final_response_without_tool_call() -> None:
    llm_payload = _valid_response(
        baggage_warnings=["LLM warning that must be ignored"],
    ).model_dump(mode="json")
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(llm_payload),
                            tool_calls=None,
                        )
                    )
                ]
            )
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

    result = await service.chat("Je pars à Rome", traveler_profile=profile)

    assert "LLM warning that must be ignored" not in result.baggage_warnings
    assert any("cabin baggage" in warning.lower() for warning in result.baggage_warnings)


def test_packing_item_battery_detected_deterministically() -> None:
    warnings = collect_packing_item_warnings(
        [
            PackingItem(
                name="power bank",
                category="electronics",
                quantity=1,
                reason="Charge devices",
                essential=True,
            )
        ],
        baggage_type="cabin",
    )

    assert any("power banks" in warning.lower() for warning in warnings)


def test_packing_item_liquid_over_100ml_detected_deterministically() -> None:
    warnings = collect_packing_item_warnings(
        [
            PackingItem(
                name="shampoo 200ml",
                category="toiletries",
                quantity=1,
                reason="Hygiene",
                essential=False,
            )
        ],
        baggage_type="cabin",
    )

    assert any("100 ml" in warning for warning in warnings)


def test_packing_item_sharp_object_detected_deterministically() -> None:
    warnings = collect_packing_item_warnings(
        [
            PackingItem(
                name="kitchen knife",
                category="sharp_objects",
                quantity=1,
                reason="Cooking",
                essential=False,
            )
        ],
        baggage_type="cabin",
    )

    assert any("sharp objects" in warning.lower() for warning in warnings)


def test_merge_stable_unique_preserves_order_and_deduplicates() -> None:
    merged = merge_stable_unique(
        ["warning-a", "warning-b"],
        ["warning-b", "warning-c"],
        ["warning-a"],
    )

    assert merged == ["warning-a", "warning-b", "warning-c"]


def test_enrich_response_adds_deterministic_profile_considerations() -> None:
    profile = _profile_with_notes()
    response = _valid_response(
        profile_considerations=["Requires insulin refrigeration verbatim"],
        packing_items=[
            PackingItem(
                name="power bank",
                category="electronics",
                quantity=1,
                reason="Charge devices",
                essential=True,
            )
        ],
    )

    enriched = enrich_packing_response(
        response=response,
        profile=profile,
        collected_baggage_warnings=collect_profile_baggage_warnings(profile),
        rules_disclaimer=RULES_DISCLAIMER,
    )

    assert any("medication transport" in item.lower() for item in enriched.profile_considerations)
    assert "insulin" not in " ".join(enriched.profile_considerations).lower()
    assert any("power banks" in warning.lower() for warning in enriched.baggage_warnings)


@pytest.mark.asyncio
async def test_share_sensitive_notes_false_keeps_notes_out_of_tool_result() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=None,
                            tool_calls=[
                                make_tool_call("call_profile", "traveler_profile", {})
                            ],
                        )
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(_valid_response().model_dump(mode="json")),
                            tool_calls=None,
                        )
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
    profile = _profile_with_notes(share_sensitive_notes_with_model=False)

    await service.chat("Je pars à Rome", traveler_profile=profile)

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_results = [message for message in second_call_messages if message.get("role") == "tool"]
    assert tool_results
    assert "insulin" not in tool_results[0]["content"].lower()
    assert "medical_or_accessibility_notes" not in tool_results[0]["content"]


@pytest.mark.asyncio
async def test_share_sensitive_notes_true_allows_tool_result_transmission() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(
        side_effect=[
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=None,
                            tool_calls=[
                                make_tool_call("call_profile", "traveler_profile", {})
                            ],
                        )
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content=json.dumps(_valid_response().model_dump(mode="json")),
                            tool_calls=None,
                        )
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
    profile = _profile_with_notes(share_sensitive_notes_with_model=True)

    await service.chat("Je pars à Rome", traveler_profile=profile)

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_results = [message for message in second_call_messages if message.get("role") == "tool"]
    payload = json.loads(tool_results[0]["content"])

    assert payload["sensitive_notes_shared_with_model"] is True
    assert payload["medical_or_accessibility_notes"] == ["Requires insulin refrigeration"]


def test_enrich_response_adds_daily_forecast_from_weather_tool() -> None:
    from datetime import date

    from app.models.weather import ForecastDay, WeatherResponse

    response = PackingResponse(
        destination="Rome",
        start_date=date(2026, 7, 21),
        end_date=date(2026, 7, 22),
        weather_summary=WeatherSummary(location="Rome", overview="Warm."),
        packing_items=[
            PackingItem(
                name="Sunscreen",
                category="hygiene",
                quantity=1,
                reason="Sun",
                essential=True,
            ),
            PackingItem(
                name="T-shirt",
                category="clothes",
                quantity=2,
                reason="Hot",
                essential=True,
            ),
        ],
        warnings=[],
        baggage_warnings=[],
        profile_considerations=[],
        rules_disclaimer=RULES_DISCLAIMER,
        language="en",
    )
    weather = WeatherResponse(
        location="Rome",
        forecast=[
            ForecastDay(date="2026-07-21", min="18°C", max="29°C", condition="Sunny"),
            ForecastDay(date="2026-07-22", min="19°C", max="30°C", condition="Clear"),
            ForecastDay(date="2026-07-23", min="17°C", max="28°C", condition="Cloudy"),
        ],
    )

    enriched = enrich_packing_response(
        response=response,
        profile=None,
        collected_baggage_warnings=[],
        rules_disclaimer=RULES_DISCLAIMER,
        weather_response=weather,
    )

    assert len(enriched.weather_summary.daily_forecast) == 2
    assert enriched.weather_summary.daily_forecast[0].date == "2026-07-21"
    assert enriched.packing_items[0].category == "Clothing"
    assert enriched.packing_items[0].name == "T-shirt"
    assert enriched.packing_items[1].category == "Toiletries"
