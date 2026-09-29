from __future__ import annotations

from datetime import date
from typing import Any

from app.models.chat import PackingResponse
from evals.evaluators.base import EvalResult, sanitize_evidence


def evaluate_dates(response: dict[str, Any], expected: dict[str, Any]) -> EvalResult:
    if expected.get("expect_invalid_dates"):
        return EvalResult(
            name="dates",
            passed=True,
            score=1.0,
            message="Invalid-date scenario acknowledged",
            evidence={"expect_invalid_dates": True},
        )

    try:
        parsed = PackingResponse.model_validate(response)
    except Exception as exc:  # noqa: BLE001
        return EvalResult(
            name="dates",
            passed=False,
            score=0.0,
            message=f"Cannot evaluate dates: {exc}",
            evidence={},
        )

    order_ok = parsed.end_date >= parsed.start_date
    iso_ok = isinstance(parsed.start_date, date) and isinstance(parsed.end_date, date)

    expected_start = expected.get("start_date")
    expected_end = expected.get("end_date")
    match_start = expected_start is None or str(parsed.start_date) == expected_start
    match_end = expected_end is None or str(parsed.end_date) == expected_end

    checks = [order_ok, iso_ok, match_start, match_end]
    score = sum(1 for ok in checks if ok) / len(checks)
    passed = all(checks)

    return EvalResult(
        name="dates",
        passed=passed,
        score=score,
        message="Dates are valid and coherent" if passed else "Date checks failed",
        evidence=sanitize_evidence(
            {
                "start_date": str(parsed.start_date),
                "end_date": str(parsed.end_date),
                "order_ok": order_ok,
                "match_start": match_start,
                "match_end": match_end,
            }
        ),
    )
