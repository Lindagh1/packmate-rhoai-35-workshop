from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.evaluators.base import weighted_score
from evals.evaluators.privacy import evaluate_privacy
from evals.evaluators.response_hygiene import evaluate_response_hygiene
from evals.evaluators.structure import evaluate_structure
from evals.runner import main, overall_score, run_deterministic

ROOT = Path(__file__).resolve().parents[2] / "evals"


def test_deterministic_runner_passes_default_threshold() -> None:
    results = run_deterministic()
    assert len(results) >= 15
    assert overall_score(results) >= 0.90
    assert all(item.passed for item in results)


def test_runner_cli_passes() -> None:
    assert main(["--mode", "deterministic", "--threshold", "0.90"]) == 0


def test_runner_cli_fails_impossible_threshold() -> None:
    assert main(["--mode", "deterministic", "--threshold", "0.999"]) == 1


def test_privacy_blocks_sensitive_note_leak() -> None:
    fixtures = json.loads((ROOT / "fixtures" / "valid_responses.json").read_text())
    # Find medication fixture
    response = next(iter(fixtures.values()))
    for fixture in fixtures.values():
        if any("medication" in c.lower() for c in fixture.get("profile_considerations", [])):
            response = fixture
            break
    result = evaluate_privacy(
        response,
        {"sensitive_notes": ["Requires insulin refrigeration"]},
        {
            "traveler_profile": {
                "medical_or_accessibility_notes": ["Requires insulin refrigeration"],
            }
        },
    )
    assert result.passed is True
    assert "Requires insulin refrigeration".lower() not in json.dumps(response).lower()


def test_hygiene_detects_think_tags() -> None:
    invalid = json.loads((ROOT / "fixtures" / "invalid_responses.json").read_text())
    dirty = invalid["hygiene_with_think_tags"]
    result = evaluate_response_hygiene(dirty, {})
    assert result.passed is False


def test_structure_rejects_invalid_dates_fixture() -> None:
    invalid = json.loads((ROOT / "fixtures" / "invalid_responses.json").read_text())
    result = evaluate_structure(
        invalid["invalid_dates_end_before_start"],
        {"expect_invalid_dates": True},
    )
    assert result.passed is True
    assert result.score == 1.0


def test_weighted_score_bounds() -> None:
    from evals.evaluators.base import EvalResult

    results = [
        EvalResult("structure", True, 1.0, "ok", {}),
        EvalResult("dates", True, 1.0, "ok", {}),
        EvalResult("weather_alignment", True, 1.0, "ok", {}),
        EvalResult("baggage_safety", True, 1.0, "ok", {}),
        EvalResult("profile_alignment", True, 1.0, "ok", {}),
        EvalResult("privacy", True, 1.0, "ok", {}),
        EvalResult("response_hygiene", True, 1.0, "ok", {}),
    ]
    assert weighted_score(results) == 1.0
