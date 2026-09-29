"""Baggage-policy MCP server — Streamable HTTP for OpenShift AI Gen AI Playground."""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from baggage_policy_mcp.rules import get_rules_disclaimer, lookup_baggage_rules

_TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)

mcp = FastMCP(
    "Packmate Baggage Policy",
    instructions=(
        "Demonstration baggage guidance for Packmate. Rules are generic and deterministic. "
        "Always include the disclaimer. Not airline-specific. Never send medical or sensitive notes."
    ),
    transport_security=_TRANSPORT_SECURITY,
)

BaggageTypeArg = Literal["cabin", "checked", "both", "unknown"]


@mcp.tool()
async def check_baggage_rules(
    baggage_type: BaggageTypeArg,
    item: str | None = None,
    category: str | None = None,
) -> dict:
    """Look up demonstration baggage warnings for an item or category.

    Args:
        baggage_type: cabin, checked, both, or unknown.
        item: Specific item to check (optional).
        category: Category such as liquids or electronics (optional).
    """
    result = lookup_baggage_rules(
        baggage_type=baggage_type,
        item=item,
        category=category,
        include_general_rules=False,
    )
    return result.model_dump()


@mcp.tool()
async def get_general_baggage_rules(baggage_type: BaggageTypeArg = "both") -> dict:
    """Return general demonstration weight/dimension rules plus the mandatory disclaimer.

    Args:
        baggage_type: cabin, checked, both, or unknown.
    """
    result = lookup_baggage_rules(
        baggage_type=baggage_type,
        include_general_rules=True,
    )
    return {
        "general_rules": result.general_rules,
        "disclaimer": result.disclaimer or get_rules_disclaimer(),
        "baggage_type": baggage_type,
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "baggage-policy-mcp"})


@mcp.custom_route("/ready", methods=["GET"])
async def ready(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ready", "service": "baggage-policy-mcp"})


def create_app():
    return mcp.streamable_http_app()


app = create_app()
