"""Weather MCP server — Streamable HTTP for OpenShift AI Gen AI Playground."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from weather_mcp.weather_logic import CityNotFoundError, WeatherToolError, fetch_weather

# OpenShift Routes and in-cluster Service DNS use dynamic Host headers.
# DNS rebinding protection is disabled; TLS terminates at the OpenShift router.
_TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

mcp = FastMCP(
    "Packmate Weather",
    instructions=(
        "Demonstration weather tools for Packmate. Uses the public Open-Meteo API. "
        "No credentials are required."
    ),
    transport_security=_TRANSPORT_SECURITY,
)


@mcp.tool()
async def get_weather(city: str, days: int = 14) -> dict:
    """Fetch up to 14 days of weather forecast for a city.

    Args:
        city: City name to geocode and forecast.
        days: Number of forecast days (1-14, default 14).
    """
    try:
        result = await fetch_weather(city, days)
        return result.model_dump()
    except CityNotFoundError as exc:
        return {"error": str(exc), "error_code": "city_not_found"}
    except WeatherToolError as exc:
        return {"error": str(exc), "error_code": "weather_unavailable"}


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "weather-mcp"})


@mcp.custom_route("/ready", methods=["GET"])
async def ready(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ready", "service": "weather-mcp"})


def create_app():
    """ASGI app exposing Streamable HTTP MCP at /mcp plus health probes."""
    return mcp.streamable_http_app()


app = create_app()
