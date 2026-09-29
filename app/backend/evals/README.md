# Packmate agent evaluations

Deterministic quality gate for packing responses.

## Modes

### Deterministic (CI)

Uses fixtures under `fixtures/` and scenarios under `datasets/`.

```bash
cd backend
.venv/bin/python -m evals.runner --mode deterministic
.venv/bin/python -m evals.runner --mode deterministic --threshold 0.95
.venv/bin/python -m evals.runner --mode deterministic --report-json evals/reports/latest.json
```

### Live (manual only)

Calls a Packmate API. Never enabled by default. Never required by pytest.

```bash
.venv/bin/python -m evals.runner --mode live --base-url http://localhost:8000 --threshold 0.90
```

## Scoring

Weighted average of evaluators:

| Evaluator | Weight |
|-----------|--------|
| structure | 20% |
| dates | 10% |
| weather_alignment | 10% |
| baggage_safety | 20% |
| profile_alignment | 15% |
| privacy | 20% |
| response_hygiene | 5% |

Overall score = mean of scenario scores. Default threshold: **0.90**.
