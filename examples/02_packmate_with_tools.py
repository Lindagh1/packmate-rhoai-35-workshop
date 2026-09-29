#!/usr/bin/env python3
"""Call the deployed Packmate application from Python."""

from __future__ import annotations

import json
import os
import sys
from urllib import request

packmate_api_url = os.environ.get(
    "PACKMATE_API_URL",
    "http://packmate-backend.packmate-lab.svc.cluster.local:8080/api/v1/chat",
)

request_payload = {
    "message": "I am going to Rome next week with cabin baggage only. Check the weather and tell me if I can take a 150 ml bottle and a power bank.",
    "traveler_profile": {
        "trip_type": "leisure",
        "baggage_type": "cabin",
        "activities": ["walking", "museum"],
    },
}

body = json.dumps(request_payload).encode("utf-8")
http_request = request.Request(
    packmate_api_url,
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with request.urlopen(http_request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception as exc:  # noqa: BLE001
    print(f"Packmate request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc

print("Packmate application response")
print("=============================")
print(f"Destination: {payload.get('destination')}")
print(f"Language: {payload.get('language')}")
print()
print("Warnings:")
for item in payload.get("warnings", []):
    print(f"- {item}")
print()
print("Baggage warnings:")
for item in payload.get("baggage_warnings", []):
    print(f"- {item}")
print()
print("Packing items:")
for item in payload.get("packing_items", [])[:8]:
    print(f"- {item['name']}: {item['reason']}")
