import json
import logging

from app.agent.context import ToolContext
from app.observability import TOOL_CALLS, TOOL_DURATION, Timer, span
from app.tools.adapters import build_baggage_adapter, build_weather_adapter
from app.tools.mcp_client import MCPClientError
from app.tools.traveler_profile import lookup_traveler_profile
from app.tools.weather import CityNotFoundError, WeatherToolError

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Fetch up to 14 days of weather forecast for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "days": {
                        "type": "integer",
                        "description": "Number of forecast days (1-14, default 14)",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "baggage_rules",
            "description": (
                "Look up generic demonstration baggage rules for cabin or checked baggage. "
                "Use this for security and airline policy guidance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "baggage_type": {
                        "type": "string",
                        "enum": ["cabin", "checked", "both"],
                        "description": "Baggage type to evaluate",
                    },
                    "item": {
                        "type": "string",
                        "description": "Specific item to check (optional)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Item category such as liquids or sharp_objects (optional)",
                    },
                    "include_general_rules": {
                        "type": "boolean",
                        "description": "Include generic weight and dimension demo rules",
                    },
                },
                "required": ["baggage_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traveler_profile",
            "description": (
                "Return the traveler profile provided in the current request. "
                "Call this to tailor packing recommendations. "
                "This tool is local to Packmate and is never exposed as a shared MCP server."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _safe_tool_log(name: str, args: dict, context: ToolContext) -> None:
    if name == "traveler_profile" and context.traveler_profile is not None:
        logger.info("Executing tool %s with profile=%s", name, context.traveler_profile.for_logging())
        return
    logger.info("Executing tool %s with args=%s", name, args)


def _coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return bool(value)


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


async def execute_tool(name: str, arguments: str, context: ToolContext) -> str:
    args = json.loads(arguments or "{}")
    _safe_tool_log(name, args, context)
    timer = Timer()
    status = "ok"
    weather = build_weather_adapter()
    baggage = build_baggage_adapter()

    try:
        with span(f"tool.{name}", {"tool_name": name}):
            if name == "get_weather":
                try:
                    days = _coerce_int(args.get("days", 14), 14)
                    result = await weather.get_weather(args["city"], days)
                    context.record_weather_result(result)
                    return json.dumps(result.model_dump())
                except CityNotFoundError as exc:
                    status = "not_found"
                    return json.dumps({"error": str(exc)})
                except (WeatherToolError, MCPClientError) as exc:
                    status = "error"
                    return json.dumps({"error": str(exc)})

            if name == "baggage_rules":
                result = await baggage.lookup(
                    baggage_type=args["baggage_type"],
                    item=args.get("item"),
                    category=args.get("category"),
                    include_general_rules=_coerce_bool(
                        args.get("include_general_rules", False)
                    ),
                )
                context.record_baggage_result(result.warnings, result.disclaimer)
                return json.dumps(result.model_dump())

            if name == "traveler_profile":
                # Always local — never forwarded to MCP servers.
                return json.dumps(lookup_traveler_profile(context.traveler_profile))

            status = "unknown"
            return json.dumps({"error": f"Unknown tool: {name}"})
    finally:
        TOOL_CALLS.labels(tool=name, status=status).inc()
        TOOL_DURATION.labels(tool=name).observe(timer.seconds())
