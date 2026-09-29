#!/usr/bin/env python3
"""Beginner-friendly shared model example for the Packmate workshop."""

from __future__ import annotations

import json
import os
import sys
from urllib import request

model_endpoint = os.environ.get(
    "PACKMATE_MODEL_BASE_URL",
    "http://llama-32-3b-instruct-predictor.my-first-model.svc.cluster.local:8080/v1",
)
model_name = os.environ.get("PACKMATE_MODEL_NAME", "llama-32-3b-instruct")

# The shared model is provided by OpenShift AI.
# We send the same kind of chat message that we use in Playground.
payload = {
    "model": model_name,
    "messages": [
        {
            "role": "system",
            "content": "You are Packmate, a concise travel packing assistant.",
        },
        {
            "role": "user",
            "content": "I am going to Rome for four days next week. What should I pack?",
        },
    ],
    "max_tokens": 300,
}

body = json.dumps(payload).encode("utf-8")
http_request = request.Request(
    model_endpoint.rstrip("/") + "/chat/completions",
    data=body,
    headers={
        "Content-Type": "application/json",
        # This shared predictor does not require a real API key in the live sandbox,
        # but OpenAI-compatible clients still expect an Authorization header.
        "Authorization": "Bearer dummy",
    },
    method="POST",
)

try:
    with request.urlopen(http_request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"Model request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc

message = result["choices"][0]["message"]["content"]
print("Packmate model response")
print("=======================")
print(message.strip())
