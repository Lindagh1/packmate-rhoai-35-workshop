from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from evals.evaluators.baggage_safety import evaluate_baggage_safety
from evals.evaluators.base import EvalResult, weighted_score
from evals.evaluators.dates import evaluate_dates
from evals.evaluators.privacy import evaluate_privacy
from evals.evaluators.profile_alignment import evaluate_profile_alignment
from evals.evaluators.response_hygiene import evaluate_response_hygiene
from evals.evaluators.structure import evaluate_structure
from evals.evaluators.weather_alignment import evaluate_weather_alignment

ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets" / "packing_scenarios.json"
VALID_FIXTURES = ROOT / "fixtures" / "valid_responses.json"
INVALID_FIXTURES = ROOT / "fixtures" / "invalid_responses.json"


@dataclass
class ScenarioResult:
    scenario_id: str
    description: str
    score: float
    passed: bool
    results: list[EvalResult]
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "score": self.score,
            "passed": self.passed,
            "tags": self.tags,
            "results": [result.to_dict() for result in self.results],
        }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_response(
    scenario: dict[str, Any],
    valid_fixtures: dict[str, Any],
    invalid_fixtures: dict[str, Any],
) -> dict[str, Any]:
    expected = scenario.get("expected_checks") or {}
    fixture_id = scenario.get("fixture_response_id")
    invalid_id = expected.get("invalid_fixture_id")
    if invalid_id:
        return invalid_fixtures[invalid_id]
    if not fixture_id:
        raise KeyError(f"Scenario {scenario.get('id')} has no fixture_response_id")
    return valid_fixtures[fixture_id]


def evaluate_response(
    response: dict[str, Any],
    expected: dict[str, Any],
    request: dict[str, Any] | None,
) -> list[EvalResult]:
    if expected.get("expect_invalid_dates"):
        return [
            evaluate_structure(response, expected),
            evaluate_dates(response, expected),
            EvalResult(
                name="weather_alignment",
                passed=True,
                score=1.0,
                message="Skipped for invalid-date fixture",
                evidence={"skipped": True},
            ),
            EvalResult(
                name="baggage_safety",
                passed=True,
                score=1.0,
                message="Skipped for invalid-date fixture",
                evidence={"skipped": True},
            ),
            EvalResult(
                name="profile_alignment",
                passed=True,
                score=1.0,
                message="Skipped for invalid-date fixture",
                evidence={"skipped": True},
            ),
            EvalResult(
                name="privacy",
                passed=True,
                score=1.0,
                message="Skipped for invalid-date fixture",
                evidence={"skipped": True},
            ),
            evaluate_response_hygiene(response, expected),
        ]

    return [
        evaluate_structure(response, expected),
        evaluate_dates(response, expected),
        evaluate_weather_alignment(response, expected),
        evaluate_baggage_safety(response, expected, request),
        evaluate_profile_alignment(response, expected, request),
        evaluate_privacy(response, expected, request),
        evaluate_response_hygiene(response, expected),
    ]


def run_deterministic() -> list[ScenarioResult]:
    scenarios = load_json(DATASETS)
    valid_fixtures = load_json(VALID_FIXTURES)
    invalid_fixtures = load_json(INVALID_FIXTURES)
    results: list[ScenarioResult] = []

    for scenario in scenarios:
        expected = scenario.get("expected_checks") or {}
        request = scenario.get("request") or {}
        response = resolve_response(scenario, valid_fixtures, invalid_fixtures)
        eval_results = evaluate_response(response, expected, request)
        score = weighted_score(eval_results)
        scenario_passed = all(item.passed for item in eval_results) and score >= 0.8

        results.append(
            ScenarioResult(
                scenario_id=str(scenario["id"]),
                description=str(scenario.get("description", "")),
                score=score,
                passed=scenario_passed,
                results=eval_results,
                tags=list(scenario.get("tags") or []),
            )
        )
    return results


def run_live(base_url: str, timeout: float = 120.0) -> list[ScenarioResult]:
    scenarios = load_json(DATASETS)
    results: list[ScenarioResult] = []
    endpoint = base_url.rstrip("/") + "/api/v1/chat/stream"

    for scenario in scenarios:
        expected = scenario.get("expected_checks") or {}
        if expected.get("expect_invalid_dates"):
            continue
        request_payload = scenario.get("request") or {}
        try:
            payload = stream_live_response(endpoint, request_payload, timeout=timeout)
            eval_results = evaluate_response(payload, expected, request_payload)
            score = weighted_score(eval_results)
            scenario_passed = all(item.passed for item in eval_results) and score >= 0.8
            results.append(
                ScenarioResult(
                    scenario_id=str(scenario["id"]),
                    description=str(scenario.get("description", "")),
                    score=score,
                    passed=scenario_passed,
                    results=eval_results,
                    tags=list(scenario.get("tags") or []),
                )
            )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            failed = EvalResult(
                name="structure",
                passed=False,
                score=0.0,
                message=f"HTTP {exc.code}",
                evidence={"status": exc.code, "detail": detail},
            )
            results.append(
                ScenarioResult(
                    scenario_id=str(scenario["id"]),
                    description=str(scenario.get("description", "")),
                    score=0.0,
                    passed=False,
                    results=[failed],
                    tags=list(scenario.get("tags") or []),
                )
            )
        except Exception as exc:  # noqa: BLE001
            failed = EvalResult(
                name="structure",
                passed=False,
                score=0.0,
                message=f"Live request failed: {type(exc).__name__}",
                evidence={},
            )
            results.append(
                ScenarioResult(
                    scenario_id=str(scenario["id"]),
                    description=str(scenario.get("description", "")),
                    score=0.0,
                    passed=False,
                    results=[failed],
                    tags=list(scenario.get("tags") or []),
                )
            )
    return results


def stream_live_response(
    endpoint: str,
    request_payload: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    """Call the public SSE endpoint and return the final completed payload."""
    body = json.dumps(request_payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    current_event = "message"
    data_lines: list[str] = []
    completed: dict[str, Any] | None = None
    stream_error: str | None = None

    def flush_event() -> None:
        nonlocal current_event, data_lines, completed, stream_error
        if not data_lines:
            current_event = "message"
            return
        raw = "\n".join(data_lines).strip()
        data_lines = []
        if not raw:
            current_event = "message"
            return
        payload = json.loads(raw)
        if current_event == "completed":
            if not isinstance(payload, dict):
                raise ValueError("Completed SSE payload was not a JSON object")
            completed = payload
        elif current_event == "error":
            if isinstance(payload, dict):
                stream_error = str(payload.get("message") or "Streaming chat failed")
            else:
                stream_error = str(payload)
        current_event = "message"

    with request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                flush_event()
                if stream_error:
                    raise RuntimeError(stream_error)
                if completed is not None:
                    return completed
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                current_event = line.partition(":")[2].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line.partition(":")[2].lstrip())

    flush_event()
    if stream_error:
        raise RuntimeError(stream_error)
    if completed is None:
        raise RuntimeError("Stream ended before a completed event was received")
    return completed


def overall_score(scenario_results: list[ScenarioResult]) -> float:
    if not scenario_results:
        return 0.0
    return round(sum(item.score for item in scenario_results) / len(scenario_results), 4)


def print_report(scenario_results: list[ScenarioResult], threshold: float) -> int:
    score = overall_score(scenario_results)
    print("Packmate evaluation quality gate")
    print(f"Scenarios: {len(scenario_results)}")
    print(f"Overall score: {score:.4f}")
    print(f"Threshold: {threshold:.4f}")
    print("-" * 60)
    for item in scenario_results:
        status = "PASS" if item.passed else "FAIL"
        print(f"[{status}] {item.scenario_id:28} score={item.score:.4f}  {item.description}")
        for result in item.results:
            mark = "ok" if result.passed else "xx"
            print(f"    - {result.name:18} {mark} {result.score:.2f} {result.message}")
    print("-" * 60)
    if score >= threshold:
        print("QUALITY GATE PASSED")
        return 0
    print("QUALITY GATE FAILED")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Packmate evaluation quality gate")
    parser.add_argument("--mode", choices=["deterministic", "live"], default="deterministic")
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--base-url", default="", help="Packmate API base URL for live mode")
    parser.add_argument("--report-json", default="", help="Optional JSON report output path")
    args = parser.parse_args(argv)

    if args.mode == "live":
        if not args.base_url:
            print("Live mode requires --base-url", file=sys.stderr)
            return 2
        scenario_results = run_live(args.base_url)
    else:
        scenario_results = run_deterministic()

    exit_code = print_report(scenario_results, args.threshold)

    if args.report_json:
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": args.mode,
            "threshold": args.threshold,
            "overall_score": overall_score(scenario_results),
            "passed": exit_code == 0,
            "scenarios": [item.to_dict() for item in scenario_results],
        }
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote report: {report_path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
