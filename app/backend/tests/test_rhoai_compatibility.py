"""Compatibility tests for RHOAI 3.4 MCP SDK and json-repair pins."""

from __future__ import annotations

import importlib
import inspect
import re
from importlib.metadata import version as pkg_version

import pytest


def test_mcp_version_is_rhoai_supported() -> None:
    version = pkg_version("mcp")
    assert re.match(r"^1\.", version), f"MCP major must be 1.x for RHOAI 3.4, got {version}"
    assert not version.startswith("2."), f"MCP 2.x is incompatible with Packmate lab pin ({version})"
    assert version == "1.27.2", f"expected mcp==1.27.2, got {version}"


def test_mcp_streamable_http_client_symbol() -> None:
    mod = importlib.import_module("mcp.client.streamable_http")
    assert hasattr(mod, "streamable_http_client"), (
        "MCP SDK missing streamable_http_client (v1 API)"
    )
    client = mod.streamable_http_client
    assert callable(client)
    # Context-manager factory used by Packmate: async with streamable_http_client(url)
    assert inspect.isfunction(client) or inspect.iscoroutinefunction(client) or callable(client)


def test_packmate_mcp_client_imports_supported_symbol() -> None:
    from app.tools import mcp_client

    src = inspect.getsource(mcp_client)
    assert "from mcp.client.streamable_http import streamable_http_client" in src
    # Reject the legacy symbol name if it appears as an identifier import target.
    assert "import streamablehttp_client" not in src
    assert "streamablehttp_client(" not in src
    assert mcp_client.streamable_http_client is not None


def test_json_repair_version_is_rhoai_supported() -> None:
    version = pkg_version("json-repair")
    assert version == "0.25.3", f"expected json-repair==0.25.3, got {version}"


def test_json_repair_loads_api_compatible() -> None:
    from json_repair import loads as repair_loads

    assert repair_loads('{"a": 1}') == {"a": 1}
    repaired = repair_loads('{"overview": "Mild "sunny" day."}')
    assert isinstance(repaired, dict)
    assert repaired.get("overview") == 'Mild "sunny" day.'


def test_json_repair_unrecoverable_input() -> None:
    from json_repair import loads as repair_loads

    # Completely non-JSON input should not silently invent a packing payload.
    result = repair_loads("not-json-at-all")
    assert not isinstance(result, dict) or "packing_items" not in result


def test_parser_json_repair_valid_and_malformed() -> None:
    import json

    from app.agent.exceptions import ParseError
    from app.agent.parser import parse_packing_response
    from app.tools.baggage import load_baggage_rules

    rules_disclaimer = load_baggage_rules()["disclaimer"]

    valid = {
        "destination": "Lisbon",
        "start_date": "2026-07-20",
        "end_date": "2026-07-22",
        "weather_summary": {"location": "Lisbon", "overview": "Mild"},
        "packing_items": [
            {
                "name": "Power bank",
                "category": "Electronics",
                "quantity": 1,
                "reason": "Keep devices charged",
                "essential": True,
            }
        ],
        "warnings": [],
        "baggage_warnings": [],
        "profile_considerations": [],
        "rules_disclaimer": rules_disclaimer,
        "language": "en",
    }
    assert parse_packing_response(json.dumps(valid)).destination == "Lisbon"

    broken = (
        '{"destination": "Lisbon", "start_date": "2026-07-20", '
        '"end_date": "2026-07-22", '
        '"weather_summary": {"location": "Lisbon", "overview": "Mild "sunny" day."}, '
        '"packing_items": [{"name": "Power bank", "category": "Electronics", '
        '"quantity": 1, "reason": "Keep devices charged", "essential": true}], '
        '"warnings": [], "baggage_warnings": [], "profile_considerations": [], '
        '"rules_disclaimer": '
        + json.dumps(rules_disclaimer)
        + ', "language": "en"}'
    )
    assert parse_packing_response(broken).destination == "Lisbon"

    with pytest.raises(ParseError):
        parse_packing_response("definitely-not-json")
