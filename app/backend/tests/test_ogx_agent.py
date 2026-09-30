from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agent.config import LLMSettings
from app.agent.ogx_service import OGXAgentService
from app.models.profile import TravelerProfile
from app.tools.settings import ToolSettings


def _settings() -> LLMSettings:
    return LLMSettings(
        base_url="http://ogx.example/v1",
        model="vllm-inference-1/llama-32-3b-instruct",
        api_key="dummy",
    )


def _tool_settings() -> ToolSettings:
    return ToolSettings(
        mode="mcp",
        weather_mcp_url="http://weather.packmate-lab.svc.cluster.local:8080/mcp",
        baggage_mcp_url="http://baggage.packmate-lab.svc.cluster.local:8080/mcp",
        max_retries=0,
    )


def _response_message(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="message",
        content=[SimpleNamespace(text=text)],
    )


def _mcp_call(name: str, output: dict) -> SimpleNamespace:
    return SimpleNamespace(
        type="mcp_call",
        name=name,
        output=json.dumps(output),
    )


@pytest.mark.asyncio
async def test_ogx_agent_uses_mcp_outputs_and_returns_packing_response() -> None:
    payload = {
        "destination": "Rome",
        "start_date": "2026-10-01",
        "end_date": "2026-10-04",
        "weather_summary": {
            "location": "Rome",
            "overview": "Warm weather.",
        },
        "packing_items": [
            {
                "name": "T-shirt",
                "category": "Clothing",
                "quantity": 3,
                "reason": "Warm days",
                "essential": True,
            }
        ],
        "warnings": [],
        "baggage_warnings": [],
        "profile_considerations": [],
        "rules_disclaimer": "",
        "language": "en",
    }

    response = SimpleNamespace(
        output=[
            _mcp_call(
                "get_weather",
                {
                    "location": "Rome",
                    "forecast": [
                        {
                            "date": "2026-10-01",
                            "min": "16°C",
                            "max": "28°C",
                            "condition": "Clear",
                        }
                    ],
                },
            ),
            _mcp_call(
                "check_baggage_rules",
                {
                    "warnings": [
                        "Demo rule: liquids in cabin baggage must be in containers of 100 ml or less."
                    ],
                    "matched_rule_ids": ["liquids_cabin"],
                    "general_rules": [],
                    "disclaimer": "DEMONSTRATION RULES ONLY.",
                },
            ),
            _response_message(json.dumps(payload)),
        ]
    )

    mock_client = MagicMock()
    mock_client.responses.create = MagicMock(return_value=response)

    service = OGXAgentService(
        settings=_settings(),
        tool_settings=_tool_settings(),
        client=mock_client,
    )

    result = await service.chat(
        "I am travelling to Rome next week. Check the weather and tell me if I can take a 150 ml liquid.",
        TravelerProfile(
            trip_type="leisure",
            baggage_type="cabin",
            activities=["walking"],
        ),
    )

    assert result.destination == "Rome"
    assert result.weather_summary.location == "Rome"
    assert result.rules_disclaimer == "DEMONSTRATION RULES ONLY."
    assert any("100 ml" in warning for warning in result.baggage_warnings)
    assert mock_client.responses.create.call_count == 3
    first_kwargs = mock_client.responses.create.call_args_list[0].kwargs
    second_kwargs = mock_client.responses.create.call_args_list[1].kwargs
    final_kwargs = mock_client.responses.create.call_args_list[2].kwargs
    assert first_kwargs["model"] == "vllm-inference-1/llama-32-3b-instruct"
    assert first_kwargs["tools"][0]["type"] == "mcp"
    assert first_kwargs["tools"][0]["allowed_tools"] == ["get_weather"]
    assert second_kwargs["tools"][0]["allowed_tools"] == ["check_baggage_rules"]
    assert final_kwargs["tools"] == []

