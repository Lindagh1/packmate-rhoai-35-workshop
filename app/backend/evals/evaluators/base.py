from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class EvalResult:
    name: str
    passed: bool
    score: float
    message: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(float(self.score), 4)
        return payload


WEIGHTS: dict[str, float] = {
    "structure": 0.20,
    "dates": 0.10,
    "weather_alignment": 0.10,
    "baggage_safety": 0.20,
    "profile_alignment": 0.15,
    "privacy": 0.20,
    "response_hygiene": 0.05,
}


def weighted_score(results: list[EvalResult]) -> float:
    total = 0.0
    weight_sum = 0.0
    by_name = {result.name: result for result in results}
    for name, weight in WEIGHTS.items():
        if name not in by_name:
            continue
        total += by_name[name].score * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return round(total / weight_sum, 4)


def sanitize_evidence(value: Any) -> Any:
    """Keep evidence free of sensitive notes and raw user content."""
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(
                token in lowered
                for token in (
                    "medical",
                    "note",
                    "message",
                    "prompt",
                    "token",
                    "password",
                    "api_key",
                )
            ):
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = sanitize_evidence(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_evidence(item) for item in value[:20]]
    if isinstance(value, str) and len(value) > 240:
        return value[:240] + "…"
    return value
