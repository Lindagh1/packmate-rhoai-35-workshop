from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.models.chat import PackingResponse
from evals.evaluators.base import EvalResult, sanitize_evidence


def evaluate_structure(response: dict[str, Any], expected: dict[str, Any]) -> EvalResult:
    if expected.get("expect_invalid_dates"):
        try:
            PackingResponse.model_validate(response)
        except ValidationError:
            return EvalResult(
                name="structure",
                passed=True,
                score=1.0,
                message="Invalid payload correctly rejected by schema",
                evidence={"expect_invalid_dates": True, "rejected": True},
            )
        return EvalResult(
            name="structure",
            passed=False,
            score=0.0,
            message="Expected schema rejection for invalid dates",
            evidence={"expect_invalid_dates": True, "rejected": False},
        )

    try:
        parsed = PackingResponse.model_validate(response)
    except ValidationError as exc:
        return EvalResult(
            name="structure",
            passed=False,
            score=0.0,
            message=f"Schema validation failed: {exc.error_count()} error(s)",
            evidence=sanitize_evidence({"errors": exc.errors()[:5]}),
        )

    essentials = [item for item in parsed.packing_items if item.essential]
    positive_qty = all(item.quantity >= 1 for item in parsed.packing_items)
    has_items = len(parsed.packing_items) > 0
    has_disclaimer = bool(parsed.rules_disclaimer.strip())
    has_language = bool(parsed.language.strip())

    checks = {
        "has_packing_items": has_items,
        "has_essential_items": len(essentials) > 0,
        "positive_quantities": positive_qty,
        "has_disclaimer": has_disclaimer,
        "has_language": has_language,
    }
    score = sum(1 for ok in checks.values() if ok) / len(checks)
    require_essentials = expected.get("require_essential_items", True)
    passed = positive_qty and has_disclaimer and has_language and (
        (has_items and len(essentials) > 0) if require_essentials else True
    )

    return EvalResult(
        name="structure",
        passed=passed and score >= 0.8,
        score=score,
        message="Structured PackingResponse is valid" if passed else "Structure checks failed",
        evidence=sanitize_evidence(
            {
                "item_count": len(parsed.packing_items),
                "essential_count": len(essentials),
                "checks": checks,
            }
        ),
    )
