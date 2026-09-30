from __future__ import annotations

import os

from app.agent.ogx_service import OGXAgentService
from app.agent.service import AgentService


def create_agent_service():
    runtime_mode = (os.getenv("PACKMATE_RUNTIME_MODE") or "legacy").strip().lower()
    if runtime_mode == "ogx":
        return OGXAgentService()
    return AgentService()

