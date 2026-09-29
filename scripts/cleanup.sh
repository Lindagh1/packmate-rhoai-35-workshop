#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"

APP_LABEL_KEY="${WORKSHOP_PART_OF_LABEL%%=*}"
APP_LABEL_VALUE="${WORKSHOP_PART_OF_LABEL#*=}"

printf 'Cleaning workshop-owned resources from %s\n' "${WORKSHOP_NAMESPACE}"

oc delete route,service,deployment,buildconfig,imagestream,configmap,secret -n "${WORKSHOP_NAMESPACE}" \
  -l "${APP_LABEL_KEY}=${APP_LABEL_VALUE}" --ignore-not-found

python3 - <<'PY' "${MCP_CONFIG_NAMESPACE}"
import json
import subprocess
import sys
import tempfile

ns = sys.argv[1]
result = subprocess.run(
    ["oc", "get", "configmap", "gen-ai-aa-mcp-servers", "-n", ns, "-o", "json"],
    capture_output=True,
    text=True,
    check=False,
)
if result.returncode != 0:
    raise SystemExit(0)
obj = json.loads(result.stdout)
data = dict(obj.get("data") or {})
data.pop("Packmate-Weather-MCP", None)
data.pop("Packmate-Baggage-Policy-MCP", None)
obj["data"] = data
path = tempfile.mktemp(suffix=".json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(obj, handle)
subprocess.check_call(["oc", "apply", "-f", path], stdout=subprocess.DEVNULL)
subprocess.check_call(["rm", "-f", path])
PY

printf 'Cleanup complete. Shared model in %s was not modified.\n' "${MODEL_NAMESPACE}"
