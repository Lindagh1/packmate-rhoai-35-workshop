"""Contract, failure, timeout, and privacy tests for MCP tool adapters."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.weather import ForecastDay, WeatherResponse
from app.tools.adapters import MCPBaggageAdapter, MCPWeatherAdapter
from app.tools.mcp_client import MCPClientError, assert_safe_mcp_arguments, call_mcp_tool
from app.tools.settings import ToolSettings
from app.tools.weather import CityNotFoundError


def test_default_tool_mode_is_local(monkeypatch):
    monkeypatch.delenv("PACKMATE_TOOL_MODE", raising=False)
    assert ToolSettings.from_env().mode == "local"


def test_mcp_mode_from_env(monkeypatch):
    monkeypatch.setenv("PACKMATE_TOOL_MODE", "mcp")
    monkeypatch.setenv("PACKMATE_WEATHER_MCP_URL", "http://weather.example/mcp")
    monkeypatch.setenv("PACKMATE_BAGGAGE_MCP_URL", "http://baggage.example/mcp")
    settings = ToolSettings.from_env()
    assert settings.mode == "mcp"
    assert settings.weather_mcp_url.endswith("/mcp")


def test_refuse_sensitive_keys_in_mcp_arguments():
    with pytest.raises(MCPClientError):
        assert_safe_mcp_arguments(
            {
                "item": "power bank",
                "medical_or_accessibility_notes": ["takes insulin"],
            }
        )


def test_refuse_nested_sensitive_marker():
    with pytest.raises(MCPClientError):
        assert_safe_mcp_arguments({"payload": {"medical_or_accessibility_notes": ["x"]}})


@pytest.mark.asyncio
async def test_mcp_weather_contract_maps_structured_result():
    settings = ToolSettings(mode="mcp", weather_mcp_url="http://weather/mcp", max_retries=0)
    adapter = MCPWeatherAdapter(settings)
    fake = {
        "location": "Rome",
        "forecast": [{"date": "2026-07-16", "min": "18°C", "max": "28°C", "condition": "Clear"}],
    }
    with patch("app.tools.adapters.call_mcp_tool", AsyncMock(return_value=fake)) as mocked:
        result = await adapter.get_weather("Rome", days=1)
    assert isinstance(result, WeatherResponse)
    assert result.location == "Rome"
    mocked.assert_awaited_once()
    args = mocked.await_args.args
    assert args[1] == "get_weather"
    assert "medical" not in str(mocked.await_args).lower()


@pytest.mark.asyncio
async def test_mcp_weather_city_not_found():
    settings = ToolSettings(mode="mcp", weather_mcp_url="http://weather/mcp", max_retries=0)
    adapter = MCPWeatherAdapter(settings)
    with patch(
        "app.tools.adapters.call_mcp_tool",
        AsyncMock(return_value={"error": "City 'X' not found.", "error_code": "city_not_found"}),
    ):
        with pytest.raises(CityNotFoundError):
            await adapter.get_weather("X")


@pytest.mark.asyncio
async def test_mcp_baggage_contract_check_tool():
    settings = ToolSettings(mode="mcp", baggage_mcp_url="http://baggage/mcp", max_retries=0)
    adapter = MCPBaggageAdapter(settings)
    fake = {
        "warnings": ["Demo rule: spare lithium batteries..."],
        "matched_rule_ids": ["external_batteries"],
        "general_rules": [],
        "disclaimer": "DEMONSTRATION RULES ONLY.",
    }
    with patch("app.tools.adapters.call_mcp_tool", AsyncMock(return_value=fake)) as mocked:
        result = await adapter.lookup(baggage_type="checked", item="power bank")
    assert result.matched_rule_ids == ["external_batteries"]
    assert mocked.await_args.args[1] == "check_baggage_rules"
    assert "medical_or_accessibility_notes" not in mocked.await_args.args[2]


@pytest.mark.asyncio
async def test_mcp_network_failure_retries_then_errors():
    with patch(
        "app.tools.mcp_client._call_once",
        AsyncMock(side_effect=ConnectionError("boom")),
    ) as mocked:
        with pytest.raises(MCPClientError, match="unavailable"):
            await call_mcp_tool(
                "http://weather/mcp",
                "get_weather",
                {"city": "Rome"},
                timeout_seconds=1,
                max_retries=2,
            )
    assert mocked.await_count == 3


@pytest.mark.asyncio
async def test_mcp_timeout():
    async def slow(*_args, **_kwargs):
        await asyncio.sleep(0.2)
        return {"location": "Rome", "forecast": []}

    with patch("app.tools.mcp_client._call_once", side_effect=slow):
        with pytest.raises(MCPClientError, match="unavailable"):
            await call_mcp_tool(
                "http://weather/mcp",
                "get_weather",
                {"city": "Rome"},
                timeout_seconds=0.05,
                max_retries=0,
            )


@pytest.mark.asyncio
async def test_sensitive_notes_never_sent_on_baggage_mcp_path():
    """Even if a buggy caller adds notes, the client must refuse."""
    with pytest.raises(MCPClientError):
        await call_mcp_tool(
            "http://baggage/mcp",
            "check_baggage_rules",
            {
                "baggage_type": "cabin",
                "item": "inhaler",
                "medical_or_accessibility_notes": ["fictional asthma note"],
            },
            max_retries=0,
        )


@pytest.mark.asyncio
async def test_local_adapters_still_used_by_default(monkeypatch):
    monkeypatch.delenv("PACKMATE_TOOL_MODE", raising=False)
    from app.tools.adapters import LocalWeatherAdapter, build_weather_adapter

    assert isinstance(build_weather_adapter(), LocalWeatherAdapter)


def test_forecast_day_roundtrip_for_contract():
    day = ForecastDay(date="2026-07-16", min="1°C", max="2°C", condition="Snow")
    assert day.condition == "Snow"
