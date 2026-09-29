from __future__ import annotations

from typing import Any

from app.models.chat import PackingResponse
from evals.evaluators.base import EvalResult, sanitize_evidence


def evaluate_profile_alignment(
    response: dict[str, Any],
    expected: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> EvalResult:
    try:
        parsed = PackingResponse.model_validate(response)
    except Exception as exc:  # noqa: BLE001
        return EvalResult(
            name="profile_alignment",
            passed=False,
            score=0.0,
            message=f"Cannot evaluate profile: {exc}",
            evidence={},
        )

    profile = (request or {}).get("traveler_profile") or {}
    trip_type = str(profile.get("trip_type") or expected.get("trip_type") or "").lower()
    activities = [
        str(activity).lower()
        for activity in (profile.get("activities") or expected.get("activities") or [])
    ]

    blob = " ".join(
        [
            " ".join(parsed.profile_considerations),
            " ".join(item.name for item in parsed.packing_items),
            " ".join(item.reason for item in parsed.packing_items),
            " ".join(item.category for item in parsed.packing_items),
        ]
    ).lower()

    if expected.get("profile_absent"):
        return EvalResult(
            name="profile_alignment",
            passed=True,
            score=1.0,
            message="No traveler profile expected",
            evidence={"profile_absent": True},
        )

    checks_passed = 0
    checks_total = 0

    if trip_type == "business":
        checks_total += 1
        business_hits = any(
            token in blob
            for token in (
                "business",
                "professional",
                "formal",
                "shirt",
                "chemise",
                "costume",
                "tenue",
            )
        )
        checks_passed += int(business_hits)
    elif trip_type == "leisure":
        checks_total += 1
        leisure_hits = any(
            token in blob
            for token in ("leisure", "casual", "vacation", "loisirs", "détente", "detente")
        ) or len(parsed.packing_items) > 0
        checks_passed += int(leisure_hits)

    for activity in activities:
        checks_total += 1
        checks_passed += int(activity in blob or activity.rstrip("s") in blob)

    if checks_total == 0:
        score = 1.0 if parsed.packing_items else 0.5
        passed = score >= 0.8
    else:
        score = checks_passed / checks_total
        passed = score >= 0.5

    return EvalResult(
        name="profile_alignment",
        passed=passed,
        score=score,
        message="Profile alignment acceptable" if passed else "Profile alignment weak",
        evidence=sanitize_evidence(
            {
                "trip_type": trip_type or None,
                "activity_count": len(activities),
                "checks_passed": checks_passed,
                "checks_total": checks_total,
            }
        ),
    )
