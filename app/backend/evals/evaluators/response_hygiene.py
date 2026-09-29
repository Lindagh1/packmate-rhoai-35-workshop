from __future__ import annotations

import re
from typing import Any

from evals.evaluators.base import EvalResult, sanitize_evidence

_THINK_RE = re.compile(r"<think>|<redacted_thinking>|</think>", re.IGNORECASE)
_MARKDOWN_FENCE_RE = re.compile(r"```")
_REASONING_RE = re.compile(
    r"\b(chain of thought|let me think|internal reasoning|as an ai)\b",
    re.IGNORECASE,
)


def evaluate_response_hygiene(
    response: dict[str, Any] | str,
    expected: dict[str, Any],
) -> EvalResult:
    raw = response if isinstance(response, str) else str(response)
    if isinstance(response, dict):
        # Prefer inspecting serialized textual fields only.
        parts = [
            str(response.get("destination", "")),
            str((response.get("weather_summary") or {}).get("overview", "")),
            " ".join(str(item) for item in response.get("warnings", [])),
            " ".join(str(item) for item in response.get("profile_considerations", [])),
            " ".join(
                f"{item.get('name', '')} {item.get('reason', '')}"
                for item in response.get("packing_items", [])
                if isinstance(item, dict)
            ),
        ]
        raw = "\n".join(parts)

    has_think = bool(_THINK_RE.search(raw))
    has_fence = bool(_MARKDOWN_FENCE_RE.search(raw))
    has_reasoning = bool(_REASONING_RE.search(raw))

    if expected.get("expect_hygiene_failure"):
        # Fixture intentionally dirty.
        score = 0.0 if (has_think or has_fence or has_reasoning) else 1.0
        passed = score == 0.0
        return EvalResult(
            name="response_hygiene",
            passed=passed,
            score=0.0 if passed else 1.0,
            message="Hygiene failure fixture detected" if passed else "Expected dirty fixture",
            evidence={"has_think": has_think, "has_fence": has_fence},
        )

    deductions = sum([has_think, has_fence, has_reasoning])
    score = max(0.0, 1.0 - deductions * 0.5)
    passed = deductions == 0

    return EvalResult(
        name="response_hygiene",
        passed=passed,
        score=score,
        message="Response hygiene clean" if passed else "Response hygiene issues found",
        evidence=sanitize_evidence(
            {
                "has_think_tags": has_think,
                "has_markdown_fence": has_fence,
                "has_internal_reasoning": has_reasoning,
            }
        ),
    )
