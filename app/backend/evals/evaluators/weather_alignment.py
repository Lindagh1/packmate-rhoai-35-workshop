from __future__ import annotations

from typing import Any

from app.models.chat import PackingResponse
from evals.evaluators.base import EvalResult, sanitize_evidence

_HOT_HINTS = ("hot", "sun", "warm", "heat", "chaud", "soleil", "été", "ete")
_COLD_HINTS = ("cold", "snow", "winter", "froid", "neige", "hiver", "coat", "manteau")
_RAIN_HINTS = ("rain", "wet", "pluie", "umbrella", "imperméable", "impermeable", "poncho")


def evaluate_weather_alignment(
    response: dict[str, Any],
    expected: dict[str, Any],
) -> EvalResult:
    try:
        parsed = PackingResponse.model_validate(response)
    except Exception as exc:  # noqa: BLE001
        return EvalResult(
            name="weather_alignment",
            passed=False,
            score=0.0,
            message=f"Cannot evaluate weather: {exc}",
            evidence={},
        )

    climate = str(expected.get("climate", "any")).lower()
    text_blob = " ".join(
        [
            parsed.weather_summary.overview,
            parsed.weather_summary.conditions or "",
            " ".join(item.name for item in parsed.packing_items),
            " ".join(item.reason for item in parsed.packing_items),
        ]
    ).lower()

    if climate == "any":
        has_overview = bool(parsed.weather_summary.overview.strip())
        has_location = bool(parsed.weather_summary.location.strip())
        score = 1.0 if has_overview and has_location else 0.5
        return EvalResult(
            name="weather_alignment",
            passed=score >= 0.8,
            score=score,
            message="Weather summary present",
            evidence=sanitize_evidence(
                {
                    "location": parsed.weather_summary.location,
                    "daily_count": len(parsed.weather_summary.daily_forecast),
                }
            ),
        )

    hints = {
        "hot": _HOT_HINTS,
        "cold": _COLD_HINTS,
        "rain": _RAIN_HINTS,
    }.get(climate, ())

    hits = sum(1 for hint in hints if hint in text_blob)
    score = min(1.0, hits / max(2, len(hints) // 3 or 1))
    if hits >= 1:
        score = max(score, 0.7)
    if hits >= 2:
        score = max(score, 0.9)

    return EvalResult(
        name="weather_alignment",
        passed=hits >= 1,
        score=score,
        message=f"Weather alignment for climate={climate}" if hits else "No climate alignment signals",
        evidence=sanitize_evidence({"climate": climate, "hint_hits": hits}),
    )
