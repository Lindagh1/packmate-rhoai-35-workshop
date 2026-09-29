"""Tool execution mode settings (local Python tools vs remote MCP servers)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ToolMode = Literal["local", "mcp"]


@dataclass(frozen=True)
class ToolSettings:
    mode: ToolMode = "local"
    weather_mcp_url: str = "http://weather-mcp:8080/mcp"
    baggage_mcp_url: str = "http://baggage-policy-mcp:8080/mcp"
    timeout_seconds: float = 10.0
    max_retries: int = 2

    @classmethod
    def from_env(cls) -> "ToolSettings":
        raw_mode = (os.getenv("PACKMATE_TOOL_MODE") or "local").strip().lower()
        mode: ToolMode = "mcp" if raw_mode == "mcp" else "local"
        return cls(
            mode=mode,
            weather_mcp_url=(
                os.getenv("PACKMATE_WEATHER_MCP_URL") or "http://weather-mcp:8080/mcp"
            ).rstrip("/"),
            baggage_mcp_url=(
                os.getenv("PACKMATE_BAGGAGE_MCP_URL") or "http://baggage-policy-mcp:8080/mcp"
            ).rstrip("/"),
            timeout_seconds=float(os.getenv("PACKMATE_MCP_TIMEOUT_SECONDS") or "10"),
            max_retries=max(0, int(os.getenv("PACKMATE_MCP_MAX_RETRIES") or "2")),
        )
