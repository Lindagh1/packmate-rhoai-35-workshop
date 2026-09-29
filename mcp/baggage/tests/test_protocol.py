"""MCP protocol and health endpoint tests for baggage-policy-mcp."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from baggage_policy_mcp.app import app, check_baggage_rules, get_general_baggage_rules, mcp


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_ready(client):
    assert client.get("/health").json()["service"] == "baggage-policy-mcp"
    assert client.get("/ready").json()["status"] == "ready"


@pytest.mark.asyncio
async def test_tools_registered():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert "check_baggage_rules" in names
    assert "get_general_baggage_rules" in names


@pytest.mark.asyncio
async def test_check_baggage_rules_tool():
    result = await check_baggage_rules(baggage_type="cabin", item="knife")
    assert "disclaimer" in result
    assert result["warnings"]


@pytest.mark.asyncio
async def test_get_general_baggage_rules_tool():
    result = await get_general_baggage_rules(baggage_type="both")
    assert result["general_rules"]
    assert "DEMONSTRATION" in result["disclaimer"]


def test_mcp_initialize(client):
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
