from __future__ import annotations

from typing import Any

from app.models.chat import PackingResponse
from app.tools.baggage import lookup_baggage_rules, resolve_baggage_type
from evals.evaluators.base import EvalResult, sanitize_evidence


def evaluate_baggage_safety(
    response: dict[str, Any],
    expected: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> EvalResult:
    try:
        parsed = PackingResponse.model_validate(response)
    except Exception as exc:  # noqa: BLE001
        return EvalResult(
            name="baggage_safety",
            passed=False,
            score=0.0,
            message=f"Cannot evaluate baggage: {exc}",
            evidence={},
        )

    profile = (request or {}).get("traveler_profile")
    baggage_type = "unknown"
    if isinstance(profile, dict) and profile.get("baggage_type"):
        baggage_type = str(profile["baggage_type"])
    elif expected.get("baggage_type"):
        baggage_type = str(expected["baggage_type"])

    # Build a tiny profile-like object for resolve helper when possible.
    class _Mini:
        def __init__(self, value: str) -> None:
            self.baggage_type = value

    resolved = resolve_baggage_type(_Mini(baggage_type) if baggage_type != "unknown" else None)

    expected_warning_substrings = [
        str(item).lower() for item in expected.get("expect_baggage_warning_substrings", [])
    ]
    warning_blob = " ".join(parsed.baggage_warnings).lower()

    missing = [needle for needle in expected_warning_substrings if needle not in warning_blob]
    has_disclaimer = "demonstration" in parsed.rules_disclaimer.lower() or bool(
        parsed.rules_disclaimer.strip()
    )

    # Deterministic recompute for flagged items.
    recomputed: list[str] = []
    for item in parsed.packing_items:
        result = lookup_baggage_rules(
            baggage_type=resolved if resolved != "unknown" else "cabin",
            item=item.name,
            category=item.category,
        )
        recomputed.extend(result.warnings)

    score = 1.0
    if expected_warning_substrings:
        score = max(0.0, 1.0 - (len(missing) / len(expected_warning_substrings)))
    if not has_disclaimer:
        score = min(score, 0.5)

    if expected.get("allow_empty_baggage_warnings"):
        passed = has_disclaimer
        score = 1.0 if passed else 0.4
    else:
        passed = has_disclaimer and not missing

    return EvalResult(
        name="baggage_safety",
        passed=passed,
        score=score,
        message="Baggage safety checks passed" if passed else "Baggage safety checks failed",
        evidence=sanitize_evidence(
            {
                "baggage_type": resolved,
                "warning_count": len(parsed.baggage_warnings),
                "missing_substrings": missing,
                "has_disclaimer": has_disclaimer,
                "recomputed_warning_count": len(recomputed),
            }
        ),
    )
