"""MCP protocol and health endpoint tests for weather-mcp."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from weather_mcp.app import app, get_weather, mcp


@pytest.fixture(scope="module")
def client():
    # StreamableHTTPSessionManager lifespan may start only once per app instance.
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_ready(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_tool_registered():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert "get_weather" in names


@pytest.mark.asyncio
async def test_get_weather_tool_structured_error(monkeypatch):
    async def boom(city: str, days: int = 14):
        from weather_mcp.weather_logic import CityNotFoundError

        raise CityNotFoundError(city)

    monkeypatch.setattr("weather_mcp.app.fetch_weather", boom)
    result = await get_weather("Atlantis")
    assert result["error_code"] == "city_not_found"
    assert "Atlantis" in result["error"]


def test_mcp_endpoint_accepts_initialize(client):
    """Streamable HTTP initialize handshake (protocol smoke)."""
    response = client.post(
        "/mcp",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "packmate-test", "version": "0.0.1"},
            },
        },
    )
    assert response.status_code in {200, 202}
    body = response.text
    assert "serverInfo" in body or "result" in body or response.status_code == 202
