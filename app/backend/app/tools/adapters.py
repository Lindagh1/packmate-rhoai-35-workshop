"""Tool adapters for local Python functions vs remote MCP servers."""

from __future__ import annotations

import asyncio
import json
from typing import Protocol

from app.models.baggage import BaggageRulesResult
from app.models.weather import WeatherResponse
from app.tools.baggage import lookup_baggage_rules
from app.tools.mcp_client import MCPClientError, call_mcp_tool
from app.tools.settings import ToolSettings
from app.tools.weather import CityNotFoundError, WeatherToolError, get_weather


class WeatherPort(Protocol):
    async def get_weather(self, city: str, days: int = 14) -> WeatherResponse: ...


class BaggagePort(Protocol):
    async def lookup(
        self,
        baggage_type: str,
        item: str | None = None,
        category: str | None = None,
        include_general_rules: bool = False,
    ) -> BaggageRulesResult: ...


class LocalWeatherAdapter:
    async def get_weather(self, city: str, days: int = 14) -> WeatherResponse:
        return await get_weather(city, days)


class LocalBaggageAdapter:
    async def lookup(
        self,
        baggage_type: str,
        item: str | None = None,
        category: str | None = None,
        include_general_rules: bool = False,
    ) -> BaggageRulesResult:
        return lookup_baggage_rules(
            baggage_type=baggage_type,  # type: ignore[arg-type]
            item=item,
            category=category,
            include_general_rules=include_general_rules,
        )


class MCPWeatherAdapter:
    def __init__(self, settings: ToolSettings) -> None:
        self._settings = settings

    async def get_weather(self, city: str, days: int = 14) -> WeatherResponse:
        payload = await call_mcp_tool(
            self._settings.weather_mcp_url,
            "get_weather",
            {"city": city, "days": days},
            timeout_seconds=self._settings.timeout_seconds,
            max_retries=self._settings.max_retries,
        )
        if payload.get("error_code") == "city_not_found" or (
            payload.get("error") and "not found" in str(payload.get("error")).lower()
        ):
            raise CityNotFoundError(city)
        if payload.get("error"):
            raise WeatherToolError(str(payload["error"]))
        return WeatherResponse.model_validate(payload)


class MCPBaggageAdapter:
    def __init__(self, settings: ToolSettings) -> None:
        self._settings = settings

    async def lookup(
        self,
        baggage_type: str,
        item: str | None = None,
        category: str | None = None,
        include_general_rules: bool = False,
    ) -> BaggageRulesResult:
        args: dict = {"baggage_type": baggage_type}
        if item is not None:
            args["item"] = item
        if category is not None:
            args["category"] = category

        try:
            if include_general_rules:
                general, checked = await asyncio.gather(
                    call_mcp_tool(
                        self._settings.baggage_mcp_url,
                        "get_general_baggage_rules",
                        {"baggage_type": baggage_type},
                        timeout_seconds=self._settings.timeout_seconds,
                        max_retries=self._settings.max_retries,
                    ),
                    call_mcp_tool(
                        self._settings.baggage_mcp_url,
                        "check_baggage_rules",
                        args,
                        timeout_seconds=self._settings.timeout_seconds,
                        max_retries=self._settings.max_retries,
                    ),
                )
                return BaggageRulesResult(
                    warnings=list(checked.get("warnings") or []),
                    matched_rule_ids=list(checked.get("matched_rule_ids") or []),
                    general_rules=list(general.get("general_rules") or []),
                    disclaimer=str(
                        general.get("disclaimer")
                        or checked.get("disclaimer")
                        or "DEMONSTRATION RULES ONLY."
                    ),
                )

            payload = await call_mcp_tool(
                self._settings.baggage_mcp_url,
                "check_baggage_rules",
                args,
                timeout_seconds=self._settings.timeout_seconds,
                max_retries=self._settings.max_retries,
            )
            return BaggageRulesResult.model_validate(payload)
        except (MCPClientError, BaseExceptionGroup) as exc:
            # Preserve deterministic disclaimer surface for the agent when MCP is down.
            return BaggageRulesResult(
                warnings=[f"Baggage policy service unavailable: {type(exc).__name__}"],
                matched_rule_ids=[],
                general_rules=[],
                disclaimer="DEMONSTRATION RULES ONLY. Baggage MCP unavailable.",
            )


def build_weather_adapter(settings: ToolSettings | None = None) -> WeatherPort:
    cfg = settings or ToolSettings.from_env()
    if cfg.mode == "mcp":
        return MCPWeatherAdapter(cfg)
    return LocalWeatherAdapter()


def build_baggage_adapter(settings: ToolSettings | None = None) -> BaggagePort:
    cfg = settings or ToolSettings.from_env()
    if cfg.mode == "mcp":
        return MCPBaggageAdapter(cfg)
    return LocalBaggageAdapter()


def weather_result_to_tool_json(result: WeatherResponse) -> str:
    return json.dumps(result.model_dump())
