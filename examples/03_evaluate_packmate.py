#!/usr/bin/env python3
"""Run the Packmate regression evaluation against the deployed application."""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from evals.runner import overall_score, run_deterministic, run_live  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Packmate workshop")
    parser.add_argument(
        "--mode",
        choices=["deterministic", "live"],
        default="deterministic",
        help="Use deterministic fixtures for the beginner path, or run a live SSE evaluation against a deployed route.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Required for --mode live. Example: https://packmate-frontend-....apps.example.com",
    )
    parser.add_argument("--threshold", type=float, default=0.90)
    args = parser.parse_args()

    if args.mode == "live":
        if not args.base_url:
            parser.error("--base-url is required for --mode live")
        results = run_live(args.base_url)
    else:
        results = run_deterministic()
    score = overall_score(results)
    passed = sum(1 for item in results if item.passed)
    total = len(results)

    print("PACKMATE WORKSHOP EVALUATION")
    print("============================")
    print()
    print(f"Mode ............. {args.mode}")
    print(f"Scenarios ........ {total}")
    print(f"Passed ........... {passed}")
    print(f"Score ............ {score:.4f}")
    print(f"Threshold ........ {args.threshold:.4f}")
    print(f"Status ........... {'PASS' if score >= args.threshold else 'FAIL'}")
    print()
    print("This is a workshop regression evaluation for Packmate.")
    print("It is not a universal model accuracy claim.")
    return 0 if score >= args.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
