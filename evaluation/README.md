# Packmate Evaluation

The deterministic evaluation logic lives in `app/backend/evals`.

This workshop uses that evaluator as an AI application regression check, not as a universal model accuracy score.

Useful entry points:

- `examples/03_evaluate_packmate.py` for the workshop-friendly wrapper
- `app/backend/evals/runner.py`

Recommended usage:

```bash
python examples/03_evaluate_packmate.py
python examples/03_evaluate_packmate.py --mode live --base-url https://<your-packmate-route>
```
