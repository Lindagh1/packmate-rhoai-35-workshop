from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable
from typing import Any

from openai import OpenAI

from app.agent.config import LLMSettings
from app.agent.context import ToolContext
from app.agent.enrichment import enrich_packing_response
from app.agent.exceptions import AgentResponseError, LLMConfigurationError, ParseError
from app.agent.parser import extract_json_text, parse_packing_response
from app.agent.progress import ProgressCallback, ProgressStage
from app.agent.prompts import (
    build_ogx_synthesis_input,
    build_ogx_synthesis_prompt,
    build_ogx_user_input,
)
from app.agent.service import AgentService
from app.models.chat import PackingResponse
from app.models.profile import TravelerProfile
from app.models.weather import WeatherResponse
from app.observability import LLM_DURATION, LLM_ERRORS, LLM_REQUESTS, Timer, span
from app.tools.baggage import get_rules_disclaimer
from app.tools.settings import ToolSettings


class OGXAgentService:
    """Packmate agent runtime that delegates model + MCP orchestration to OGX."""

    WEATHER_SERVER_LABEL = "weather"
    BAGGAGE_SERVER_LABEL = "baggage"

    def __init__(
        self,
        settings: LLMSettings | None = None,
        tool_settings: ToolSettings | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self.settings = settings or LLMSettings.from_env()
        self.tool_settings = tool_settings or ToolSettings.from_env()
        self._client = client

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        return self.settings.create_client()

    async def _emit_progress(
        self,
        on_progress: ProgressCallback | None,
        stage: ProgressStage,
    ) -> None:
        if on_progress is None:
            return
        await on_progress(stage)

    def _response_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "mcp",
                "server_label": self.WEATHER_SERVER_LABEL,
                "server_url": self.tool_settings.weather_mcp_url,
                "require_approval": "never",
                "allowed_tools": ["get_weather"],
            },
            {
                "type": "mcp",
                "server_label": self.BAGGAGE_SERVER_LABEL,
                "server_url": self.tool_settings.baggage_mcp_url,
                "require_approval": "never",
                "allowed_tools": ["check_baggage_rules"],
            },
        ]

    @staticmethod
    def _schema_format() -> dict[str, Any]:
        return {
            "format": {
                "type": "json_schema",
                "name": "packmate_packing_response",
                "schema": PackingResponse.model_json_schema(),
                "strict": True,
            }
        }

    async def _responses_create(
        self,
        client: OpenAI,
        *,
        input_text: str,
        instructions: str,
        tools: list[dict[str, Any]] | None = None,
        text: dict[str, Any] | None = None,
    ):
        timer = Timer()
        try:
            with span("llm.responses.create", {"status": "started"}):
                response = await asyncio.to_thread(
                    client.responses.create,
                    model=self.settings.model,
                    instructions=instructions,
                    input=input_text,
                    tools=tools or [],
                    text=text,
                )
            LLM_REQUESTS.labels(status="ok").inc()
            LLM_DURATION.observe(timer.seconds())
            return response
        except Exception as exc:
            LLM_REQUESTS.labels(status="error").inc()
            LLM_ERRORS.labels(error_type=type(exc).__name__).inc()
            LLM_DURATION.observe(timer.seconds())
            raise AgentResponseError(
                f"OGX request failed: {type(exc).__name__}: {str(exc)[:240]}"
            ) from exc

    @staticmethod
    def _iter_output_items(response: Any) -> Iterable[Any]:
        return getattr(response, "output", None) or []

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts: list[str] = []
        for item in OGXAgentService._iter_output_items(response):
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", None) or []:
                text = getattr(content, "text", None)
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _parse_json_blob(blob: str | None) -> dict[str, Any] | None:
        if not blob:
            return None
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _capture_tool_context(self, response: Any, context: ToolContext) -> None:
        for item in self._iter_output_items(response):
            if getattr(item, "type", None) != "mcp_call":
                continue

            name = getattr(item, "name", None)
            payload = self._parse_json_blob(getattr(item, "output", None))
            if payload is None:
                continue

            if name == "get_weather":
                try:
                    weather = WeatherResponse.model_validate(payload)
                except Exception:
                    continue
                context.record_weather_result(weather)
                continue

            if name in {"check_baggage_rules", "get_general_baggage_rules"}:
                warnings = payload.get("warnings") or []
                general_rules = payload.get("general_rules") or []
                disclaimer = payload.get("disclaimer") or get_rules_disclaimer()
                merged = [*warnings, *general_rules]
                context.record_baggage_result(merged, disclaimer)

    @staticmethod
    def _has_final_text(response: Any) -> bool:
        return bool(OGXAgentService._extract_text(response))

    async def _probe_tool_context(
        self,
        client: OpenAI,
        *,
        label: ProgressStage,
        on_progress: ProgressCallback | None,
        input_text: str,
        tool: dict[str, Any],
        instructions: str,
        context: ToolContext,
    ) -> None:
        await self._emit_progress(on_progress, label)
        response = await self._responses_create(
            client,
            input_text=input_text,
            instructions=instructions,
            tools=[tool],
        )
        self._capture_tool_context(response, context)

    def _parse_final_response(
        self,
        text: str,
        context: ToolContext,
    ) -> PackingResponse:
        helper = AgentService(settings=self.settings, client=self._get_client())
        try:
            parsed = parse_packing_response(text)
        except ParseError:
            parsed = helper._recover_payload(extract_json_text(text), context)

        if not parsed.packing_items:
            raise AgentResponseError("OGX response did not include any packing_items.")
        return enrich_packing_response(
            response=parsed,
            profile=context.traveler_profile,
            collected_baggage_warnings=context.collected_baggage_warnings,
            rules_disclaimer=context.rules_disclaimer,
            weather_response=context.weather_response,
        )

    @staticmethod
    def _build_baggage_probe_inputs(
        message: str,
        traveler_profile: TravelerProfile | None,
    ) -> list[str]:
        baggage_type = traveler_profile.baggage_type if traveler_profile else "unknown"
        lower = message.lower()
        prompts: list[str] = []

        if re.search(r"\b\d+\s*ml\b", lower) or any(
            token in lower for token in ["liquid", "bottle", "spray", "toothpaste", "shampoo"]
        ):
            prompts.append(
                "Use the baggage MCP tool exactly once to check liquid restrictions for "
                f"{baggage_type} baggage. Original request: {message}"
            )

        if "power bank" in lower or "battery" in lower:
            prompts.append(
                "Use the baggage MCP tool exactly once to check whether a power bank or "
                f"battery is allowed in {baggage_type} baggage. Original request: {message}"
            )

        if not prompts:
            prompts.append(
                "Use the baggage MCP tool exactly once for the most relevant baggage rule in "
                f"this request. Original request: {message}"
            )
        return prompts

    async def chat(
        self,
        message: str,
        traveler_profile: TravelerProfile | None = None,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> PackingResponse:
        self.settings.require_configured()
        client = self._get_client()
        context = ToolContext(traveler_profile=traveler_profile)

        await self._emit_progress(on_progress, "preparing")
        await self._probe_tool_context(
            client,
            label="weather",
            on_progress=on_progress,
            input_text=build_ogx_user_input(message, traveler_profile),
            tool=self._response_tools()[0],
            instructions=(
                "Use the available weather MCP tool when forecast data helps answer the "
                "user request. Use the tool at most once in this request."
            ),
            context=context,
        )
        for baggage_input in self._build_baggage_probe_inputs(message, traveler_profile):
            await self._probe_tool_context(
                client,
                label="baggage_rules",
                on_progress=on_progress,
                input_text=baggage_input,
                tool=self._response_tools()[1],
                instructions=(
                    "Use the available baggage MCP tool when baggage rules, liquids, batteries, "
                    "or cabin/checked baggage restrictions are relevant. Use the tool at most "
                    "once in this request."
                ),
                context=context,
            )

        await self._emit_progress(on_progress, "generating")
        final_response = await self._responses_create(
            client,
            input_text=build_ogx_synthesis_input(
                message,
                traveler_profile,
                context.weather_response,
                context.collected_baggage_warnings,
                context.rules_disclaimer,
            ),
            instructions=build_ogx_synthesis_prompt(),
            text=self._schema_format(),
        )
        final_text = self._extract_text(final_response)
        if not final_text:
            raise AgentResponseError("OGX returned no final response text.")
        return self._parse_final_response(final_text, context)

