"""Bounded retry policy for transient Packmate agent failures.

Observed public-campaign flakes (rome_cabin, lisbon_leisure, reykjavik) were
transient final-generation failures: the model returned nearly-valid JSON that
failed schema/parse after internal correction attempts, then succeeded on an
immediate manual retry. Those map to retryable AgentResponseError categories.

Never retry user validation, missing LLM config, auth failures, or deterministic
baggage-rule outcomes.
"""

from __future__ import annotations

import random
import re
from enum import Enum

from app.agent.exceptions import AgentResponseError, LLMConfigurationError


class ErrorClass(str, Enum):
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"


# Transient final-generation / transport blips seen with llama-32 in the lab.
_RETRYABLE_AGENT_PATTERNS = (
    re.compile(r"invalid agent response after \d+ attempts", re.I),
    re.compile(r"invalid json", re.I),
    re.compile(r"schema validation failed", re.I),
    re.compile(r"empty final answer", re.I),
    re.compile(r"exceeded maximum tool rounds", re.I),
    re.compile(r"empty tool_calls", re.I),
    re.compile(r"packing_items must include", re.I),
    re.compile(r"tool-shaped json", re.I),
)

_RETRYABLE_LLM_TRANSPORT = (
    re.compile(r"timeout|timed out", re.I),
    re.compile(r"connection (reset|refused|aborted|error)", re.I),
    re.compile(r"temporarily unavailable|service unavailable", re.I),
    re.compile(r"\b429\b|rate limit", re.I),
    re.compile(r"\b500\b|\b502\b|\b503\b|\b504\b", re.I),
    re.compile(r"APIConnectionError|APITimeoutError|InternalServerError", re.I),
)

_NON_RETRYABLE_AUTH = (
    re.compile(r"\b401\b|\b403\b", re.I),
    re.compile(r"authentication|unauthorized|forbidden|permission denied", re.I),
    re.compile(r"invalid api key|incorrect api key", re.I),
)

# Keep total pause short so SSE heartbeats stay healthy.
RETRY_BASE_DELAY_SECONDS = 0.35
RETRY_JITTER_SECONDS = 1.15
MAX_RETRY_ATTEMPTS = 1  # in addition to the initial attempt


def classify_agent_error(exc: BaseException) -> ErrorClass:
    """Return whether an exception may receive at most one automatic retry."""
    if isinstance(exc, LLMConfigurationError):
        return ErrorClass.NON_RETRYABLE

    text = str(exc)
    if any(pattern.search(text) for pattern in _NON_RETRYABLE_AUTH):
        return ErrorClass.NON_RETRYABLE

    if isinstance(exc, AgentResponseError):
        if any(pattern.search(text) for pattern in _RETRYABLE_AGENT_PATTERNS):
            return ErrorClass.RETRYABLE
        if text.lower().startswith("llm request failed"):
            if any(pattern.search(text) for pattern in _RETRYABLE_LLM_TRANSPORT):
                return ErrorClass.RETRYABLE
            if any(pattern.search(text) for pattern in _NON_RETRYABLE_AUTH):
                return ErrorClass.NON_RETRYABLE
            # Unknown LLM gateway failure: treat as retryable once (lab model flakes).
            return ErrorClass.RETRYABLE
        return ErrorClass.NON_RETRYABLE

    # Unexpected errors are not retried by default.
    return ErrorClass.NON_RETRYABLE


def is_retryable(exc: BaseException) -> bool:
    return classify_agent_error(exc) is ErrorClass.RETRYABLE


def retry_delay_seconds(
    *,
    base: float = RETRY_BASE_DELAY_SECONDS,
    jitter: float = RETRY_JITTER_SECONDS,
) -> float:
    """Short delay with jitter; always below a few seconds."""
    return max(0.0, base + random.uniform(0.0, max(0.0, jitter)))
