import asyncio
import json
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from app.agent.config import LLMSettings
from app.agent.context import ToolContext
from app.agent.enrichment import enrich_packing_response
from app.agent.exceptions import AgentResponseError, LLMConfigurationError, ParseError
from app.agent.parser import clean_model_output, extract_json_text, parse_packing_response
from app.agent.prompts import build_system_prompt
from app.agent.retry import MAX_RETRY_ATTEMPTS, is_retryable, retry_delay_seconds
from app.agent.tools import TOOL_DEFINITIONS, execute_tool
from app.agent.progress import ProgressCallback, ProgressStage
from app.models.chat import PackingResponse
from app.models.profile import TravelerProfile
from app.observability import (
    AGENT_RETRIES,
    AGENT_RETRY_EXHAUSTED,
    AGENT_RETRY_SUCCESS,
    BAGGAGE_WARNINGS,
    INVALID_RESPONSES,
    LLM_DURATION,
    LLM_ERRORS,
    LLM_REQUESTS,
    Timer,
    span,
)


class AgentService:
    # Keep the tool loop short: OpenShift routes on AWS Classic LB often idle-out
    # near ~60s even when haproxy.router.openshift.io/timeout is higher.
    MAX_TOOL_ROUNDS = 6
    MAX_PARSE_ATTEMPTS = 4
    MAX_COMPLETION_TOKENS = 1280
    # Final JSON answers for multi-day trips can exceed 1280 tokens on small models.
    MAX_FINAL_COMPLETION_TOKENS = 2560
    ESSENTIAL_TOOLS = frozenset({"get_weather", "baggage_rules"})
    TOOL_PRIORITY = ("get_weather", "baggage_rules", "traveler_profile")

    def __init__(
        self,
        settings: LLMSettings | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self.settings = settings or LLMSettings.from_env()
        self._client = client

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        return self.settings.create_client()

    @staticmethod
    def _tools_for_request(
        traveler_profile: TravelerProfile | None,
    ) -> list[dict[str, Any]]:
        if traveler_profile is not None:
            return TOOL_DEFINITIONS
        return [
            tool
            for tool in TOOL_DEFINITIONS
            if tool["function"]["name"] != "traveler_profile"
        ]

    @staticmethod
    def _tool_cache_key(name: str, arguments: str | None) -> tuple[str, str]:
        raw = arguments or "{}"
        try:
            normalized = json.dumps(
                json.loads(raw), sort_keys=True, separators=(",", ":")
            )
        except json.JSONDecodeError:
            normalized = raw
        return (name, normalized)

    @classmethod
    def _select_single_tool_call(
        cls,
        tool_calls: list[Any],
        completed_tools: set[str],
    ) -> Any:
        """Keep only one tool call: the llama-32 gateway rejects multi-tool history."""
        if not tool_calls:
            raise AgentResponseError("Model returned an empty tool_calls list.")
        by_name = {tool_call.function.name: tool_call for tool_call in tool_calls}
        for name in cls.TOOL_PRIORITY:
            if name in by_name and name not in completed_tools:
                return by_name[name]
        for tool_call in tool_calls:
            if tool_call.function.name not in completed_tools:
                return tool_call
        return tool_calls[0]

    @staticmethod
    def _assistant_message_to_dict(message: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in message.tool_calls
            ]
        return payload

    @staticmethod
    def _finish_reason(response: Any) -> str | None:
        choice = response.choices[0]
        return getattr(choice, "finish_reason", None)

    def _weather_summary_from_context(self, context: ToolContext) -> dict[str, Any] | None:
        weather = context.weather_response
        if weather is None:
            return None
        daily = [
            {
                "date": day.date,
                "min": day.min,
                "max": day.max,
                "condition": day.condition,
            }
            for day in weather.forecast[:7]
        ]
        mins = [day.min for day in weather.forecast if day.min]
        maxs = [day.max for day in weather.forecast if day.max]
        conditions = [day.condition for day in weather.forecast if day.condition]
        return {
            "location": weather.location,
            "overview": f"Forecast for {weather.location}.",
            "min_temperature": mins[0] if mins else None,
            "max_temperature": maxs[-1] if maxs else None,
            "conditions": ", ".join(dict.fromkeys(conditions)) if conditions else None,
            "daily_forecast": daily,
        }

    def _recover_payload(
        self,
        text: str,
        context: ToolContext,
    ) -> PackingResponse:
        """Parse model JSON, filling recoverable fields from tool context when omitted."""
        from app.agent.parser import _loads_payload

        extracted = extract_json_text(text)
        try:
            payload = _loads_payload(extracted)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON: {exc.msg}") from exc

        if not isinstance(payload, dict):
            raise ParseError("Schema validation failed: expected a JSON object")

        if payload.get("name") in (
            "get_weather",
            "baggage_rules",
            "traveler_profile",
            "check_baggage_rules",
        ) and "destination" not in payload:
            raise ParseError(
                "Schema validation failed: tool-shaped JSON is not a PackingResponse"
            )

        weather_summary = payload.get("weather_summary")
        if not isinstance(weather_summary, dict) or not weather_summary.get("location"):
            injected = self._weather_summary_from_context(context)
            if injected is not None:
                payload["weather_summary"] = injected

        if not payload.get("rules_disclaimer") and context.rules_disclaimer:
            payload["rules_disclaimer"] = context.rules_disclaimer

        try:
            return PackingResponse.model_validate(payload)
        except ValidationError as exc:
            raise ParseError(f"Schema validation failed: {exc}") from exc

    def _enrich_response(
        self,
        response: PackingResponse,
        context: ToolContext,
    ) -> PackingResponse:
        with span("enrichment.deterministic", {"language": response.language}):
            enriched = enrich_packing_response(
                response=response,
                profile=context.traveler_profile,
                collected_baggage_warnings=context.collected_baggage_warnings,
                rules_disclaimer=context.rules_disclaimer,
                weather_response=context.weather_response,
            )
        if enriched.baggage_warnings:
            BAGGAGE_WARNINGS.inc(len(enriched.baggage_warnings))
        return enriched

    async def _parse_with_retries(
        self,
        client: OpenAI,
        messages: list[dict[str, Any]],
        content: str,
        context: ToolContext,
        *,
        truncated: bool = False,
    ) -> PackingResponse:
        current_content = content
        was_truncated = truncated

        for attempt in range(self.MAX_PARSE_ATTEMPTS):
            try:
                with span("parser.packing_response", {"attempt": attempt + 1}):
                    try:
                        parsed = parse_packing_response(current_content)
                    except ParseError:
                        parsed = self._recover_payload(current_content, context)
                if not parsed.packing_items:
                    raise ParseError(
                        "packing_items must include at least one item"
                    )
                return self._enrich_response(parsed, context)
            except (ParseError, json.JSONDecodeError, ValueError) as exc:
                INVALID_RESPONSES.inc()
                if attempt >= self.MAX_PARSE_ATTEMPTS - 1:
                    raise AgentResponseError(
                        f"Invalid agent response after {self.MAX_PARSE_ATTEMPTS} attempts: {exc}"
                    ) from exc

                messages.append(
                    {
                        "role": "assistant",
                        "content": clean_model_output(current_content),
                    }
                )
                truncate_hint = (
                    " The previous answer was truncated; return a shorter complete JSON "
                    "with fewer packing_items (8–12) and a compact weather_summary."
                    if was_truncated
                    else ""
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous answer was invalid. "
                            f"Error: {exc}. "
                            "Return ONLY valid JSON matching the required schema. "
                            "Include destination, weather_summary, rules_disclaimer, "
                            "and a non-empty packing_items array (8–12 items). "
                            "Do not return tool call objects. "
                            "Do not include markdown fences or explanations."
                            f"{truncate_hint}"
                        ),
                    }
                )

                correction = await self._llm_create(
                    client,
                    messages,
                    max_tokens=self.MAX_FINAL_COMPLETION_TOKENS,
                )
                current_content = correction.choices[0].message.content or ""
                was_truncated = self._finish_reason(correction) == "length"

        raise AgentResponseError("Unable to parse agent response.")

    async def _llm_create(
        self, client: OpenAI, messages: list[dict[str, Any]], **kwargs: Any
    ):
        # Run the sync OpenAI client off the event loop so /health and /ready
        # stay responsive during long model/tool rounds.
        timer = Timer()
        kwargs.setdefault("max_tokens", self.MAX_COMPLETION_TOKENS)
        try:
            with span("llm.chat.completions", {"status": "started"}):
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=self.settings.model,
                    messages=messages,
                    **kwargs,
                )
            LLM_REQUESTS.labels(status="ok").inc()
            LLM_DURATION.observe(timer.seconds())
            return response
        except Exception as exc:
            LLM_REQUESTS.labels(status="error").inc()
            LLM_ERRORS.labels(error_type=type(exc).__name__).inc()
            LLM_DURATION.observe(timer.seconds())
            # Surface model/gateway 4xx as agent errors (HTTP 502) instead of unhandled 500.
            raise AgentResponseError(
                f"LLM request failed: {type(exc).__name__}: {str(exc)[:240]}"
            ) from exc

    async def _emit_progress(
        self,
        on_progress: ProgressCallback | None,
        stage: ProgressStage,
    ) -> None:
        if on_progress is None:
            return
        await on_progress(stage)

    async def _generate_final_json(
        self,
        client: OpenAI,
        messages: list[dict[str, Any]],
        context: ToolContext,
        on_progress: ProgressCallback | None,
    ) -> PackingResponse:
        await self._emit_progress(on_progress, "generating")
        response = await self._llm_create(
            client,
            messages,
            max_tokens=self.MAX_FINAL_COMPLETION_TOKENS,
        )
        content = response.choices[0].message.content or ""
        truncated = self._finish_reason(response) == "length"

        if truncated and content:
            # One targeted expansion retry when the first final answer hits the token cap.
            messages.append({"role": "assistant", "content": clean_model_output(content)})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous JSON was truncated. Return ONLY a complete valid "
                        "JSON object with 8–12 packing_items and a short weather_summary."
                    ),
                }
            )
            response = await self._llm_create(
                client,
                messages,
                max_tokens=self.MAX_FINAL_COMPLETION_TOKENS,
            )
            content = response.choices[0].message.content or ""
            truncated = self._finish_reason(response) == "length"

        if not content:
            raise AgentResponseError("Model returned an empty final answer.")

        return await self._parse_with_retries(
            client,
            messages,
            content,
            context,
            truncated=truncated,
        )

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
        tools = self._tools_for_request(traveler_profile)
        tool_cache: dict[tuple[str, str], str] = {}
        completed_tools: set[str] = set()

        max_attempts = 1 + MAX_RETRY_ATTEMPTS
        for attempt in range(max_attempts):
            with span(
                "agent.chat",
                {"retry_attempt": attempt, "status": "started"},
            ):
                try:
                    result = await self._chat_attempt(
                        client=client,
                        message=message,
                        context=context,
                        tools=tools,
                        tool_cache=tool_cache,
                        completed_tools=completed_tools,
                        on_progress=on_progress,
                        retry_attempt=attempt,
                    )
                    if attempt > 0:
                        AGENT_RETRY_SUCCESS.inc()
                    return result
                except LLMConfigurationError:
                    raise
                except Exception as exc:
                    if attempt < MAX_RETRY_ATTEMPTS and is_retryable(exc):
                        AGENT_RETRIES.inc()
                        await self._emit_progress(on_progress, "retrying_generation")
                        await asyncio.sleep(retry_delay_seconds())
                        continue
                    if attempt > 0 and is_retryable(exc):
                        AGENT_RETRY_EXHAUSTED.inc()
                    raise

        raise AgentResponseError("Agent retry budget exhausted.")

    def _seed_messages_from_tool_cache(
        self,
        message: str,
        tool_cache: dict[tuple[str, str], str],
        completed_tools: set[str],
    ) -> list[dict[str, Any]]:
        """Rebuild chat history from cached tool results without re-calling MCP."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": message},
        ]
        # Prefer essential tools first, then any other cached tools.
        ordered_names = [
            name
            for name in self.TOOL_PRIORITY
            if name in completed_tools
        ] + [
            name
            for name in completed_tools
            if name not in self.TOOL_PRIORITY
        ]
        for name in ordered_names:
            cached = next(
                (
                    (args, result)
                    for (cached_name, args), result in tool_cache.items()
                    if cached_name == name
                ),
                None,
            )
            if cached is None:
                continue
            args, result = cached
            call_id = f"cached_{name}"
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": args},
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result,
                }
            )
        return messages

    async def _chat_attempt(
        self,
        *,
        client: OpenAI,
        message: str,
        context: ToolContext,
        tools: list[dict[str, Any]],
        tool_cache: dict[tuple[str, str], str],
        completed_tools: set[str],
        on_progress: ProgressCallback | None,
        retry_attempt: int,
    ) -> PackingResponse:
        forced_final_nudge = False
        messages = self._seed_messages_from_tool_cache(
            message,
            tool_cache,
            completed_tools,
        )
        # On a fresh attempt with no tools yet, seed is just system+user.
        if len(messages) == 2:
            messages = [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": message},
            ]

        if retry_attempt == 0:
            await self._emit_progress(on_progress, "preparing")

        for _ in range(self.MAX_TOOL_ROUNDS):
            essentials_ready = self.ESSENTIAL_TOOLS.issubset(completed_tools)
            if essentials_ready:
                if not forced_final_nudge:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You already have weather and baggage tool results. "
                                "Return ONLY valid JSON matching the required schema now. "
                                "Do not call tools."
                            ),
                        }
                    )
                    forced_final_nudge = True
                return await self._generate_final_json(
                    client, messages, context, on_progress
                )

            create_kwargs: dict[str, Any] = {
                "tools": tools,
                "tool_choice": "auto",
                "parallel_tool_calls": False,
            }
            try:
                response = await self._llm_create(
                    client,
                    messages,
                    **create_kwargs,
                )
            except AgentResponseError as exc:
                err_text = str(exc).lower()
                # Some gateways reject the parallel_tool_calls parameter.
                if "parallel_tool_calls" in err_text or "unexpected keyword" in err_text:
                    create_kwargs.pop("parallel_tool_calls", None)
                    response = await self._llm_create(
                        client,
                        messages,
                        **create_kwargs,
                    )
                elif "single tool" in err_text:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Call only one tool at a time. "
                                "Prefer get_weather first, then baggage_rules, then final JSON."
                            ),
                        }
                    )
                    response = await self._llm_create(
                        client,
                        messages,
                        **create_kwargs,
                    )
                else:
                    raise
            assistant_message = response.choices[0].message
            tool_calls = list(assistant_message.tool_calls or [])

            if tool_calls:
                selected = self._select_single_tool_call(
                    tool_calls,
                    completed_tools,
                )
                # Rewrite history as a single tool-call turn (required by llama-32 gateway).
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [
                            {
                                "id": selected.id,
                                "type": "function",
                                "function": {
                                    "name": selected.function.name,
                                    "arguments": selected.function.arguments,
                                },
                            }
                        ],
                    }
                )

                name = selected.function.name
                if name == "get_weather":
                    await self._emit_progress(on_progress, "weather")
                elif name == "baggage_rules":
                    await self._emit_progress(on_progress, "baggage_rules")

                cache_key = self._tool_cache_key(name, selected.function.arguments)
                if cache_key in tool_cache:
                    tool_result = tool_cache[cache_key]
                else:
                    tool_result = await execute_tool(
                        name,
                        selected.function.arguments,
                        context,
                    )
                    tool_cache[cache_key] = tool_result

                completed_tools.add(name)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": selected.id,
                        "content": tool_result,
                    }
                )
                continue

            if assistant_message.content:
                await self._emit_progress(on_progress, "generating")
                return await self._parse_with_retries(
                    client,
                    messages,
                    assistant_message.content,
                    context,
                    truncated=self._finish_reason(response) == "length",
                )

        # Force a schema JSON answer without further tool calls (small models).
        messages.append(
            {
                "role": "user",
                "content": (
                    "Stop calling tools. Using the tool results already provided, "
                    "return ONLY valid JSON matching the required schema. "
                    "No markdown fences or explanations."
                ),
            }
        )
        return await self._generate_final_json(client, messages, context, on_progress)
