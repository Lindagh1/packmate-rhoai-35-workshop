#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"
packmate_assert_rhoai_35
packmate_discover_model_url

PASS_COUNT=0
FAIL_COUNT=0

pass() { printf '%-30s PASS\n' "$1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { printf '%-30s FAIL\n' "$1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

check_http() {
  local label="$1"
  local url="$2"
  local code
  code="$(curl -sk -o /dev/null -w '%{http_code}' -m 25 "${url}" || echo 000)"
  if [[ "${code}" == "200" ]]; then
    pass "${label}"
  else
    fail "${label}"
  fi
}

check_contains() {
  local label="$1"
  local command="$2"
  local needle="$3"
  if bash -lc "${command}" 2>/dev/null | grep -q "${needle}"; then
    pass "${label}"
  else
    fail "${label}"
  fi
}

printf 'PACKMATE OPENSHIFT AI 3.5 WORKSHOP\n'
printf '==================================\n\n'

[[ "$(packmate_detect_openshift_version)" == 4.20* ]] && pass "OpenShift" || fail "OpenShift"
[[ "$(packmate_detect_rhoai_version)" == 3.5* ]] && pass "OpenShift AI 3.5" || fail "OpenShift AI 3.5"
[[ "$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiStudio}')" == "true" ]] && pass "Gen AI Studio" || fail "Gen AI Studio"
oc get deployment gen-ai-ui -n redhat-ods-applications >/dev/null 2>&1 && pass "Playground" || fail "Playground"
oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" >/dev/null 2>&1 && pass "Shared Llama" || fail "Shared Llama"
[[ "$(oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')" == "True" ]] && pass "Model Ready" || fail "Model Ready"

BACKEND_POD="$(oc -n "${WORKSHOP_NAMESPACE}" get pod -l app=packmate-backend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [[ -n "${BACKEND_POD}" ]]; then
  pass "Backend pod"
else
  fail "Backend pod"
fi

model_body="$(oc -n "${WORKSHOP_NAMESPACE}" exec "${BACKEND_POD}" -- sh -lc "curl -sS -m 20 '${MODEL_BASE_URL}/models'" 2>/dev/null || true)"
if printf '%s' "${model_body}" | grep -q "${MODEL_NAME}"; then
  pass "Model endpoint"
else
  fail "Model endpoint"
fi

for name in weather-mcp baggage-policy-mcp packmate-backend packmate-frontend; do
  if oc -n "${WORKSHOP_NAMESPACE}" rollout status "deploy/${name}" --timeout=30s >/dev/null 2>&1; then
    case "${name}" in
      weather-mcp) pass "Weather MCP" ;;
      baggage-policy-mcp) pass "Baggage MCP" ;;
      packmate-backend) pass "Packmate backend" ;;
      packmate-frontend) pass "Packmate frontend" ;;
    esac
  else
    case "${name}" in
      weather-mcp) fail "Weather MCP" ;;
      baggage-policy-mcp) fail "Baggage MCP" ;;
      packmate-backend) fail "Packmate backend" ;;
      packmate-frontend) fail "Packmate frontend" ;;
    esac
  fi
done

WEATHER_ROUTE="$(oc -n "${WORKSHOP_NAMESPACE}" get route weather-mcp -o jsonpath='{.spec.host}' 2>/dev/null || true)"
BAGGAGE_ROUTE="$(oc -n "${WORKSHOP_NAMESPACE}" get route baggage-policy-mcp -o jsonpath='{.spec.host}' 2>/dev/null || true)"
FRONTEND_ROUTE="$(oc -n "${WORKSHOP_NAMESPACE}" get route packmate-frontend -o jsonpath='{.spec.host}' 2>/dev/null || true)"

check_http "Weather MCP route" "https://${WEATHER_ROUTE}/health"
check_http "Baggage MCP route" "https://${BAGGAGE_ROUTE}/health"
check_http "Packmate Route" "https://${FRONTEND_ROUTE}/"

if oc get configmap gen-ai-aa-mcp-servers -n "${MCP_CONFIG_NAMESPACE}" -o json 2>/dev/null | grep -q 'Packmate-Weather-MCP'; then
  pass "MCP registration"
else
  fail "MCP registration"
fi

if oc -n "${WORKSHOP_NAMESPACE}" exec "${BACKEND_POD}" -- sh -lc "curl -sS -m 20 http://weather-mcp:8080/health" | grep -q '"status":"ok"'; then
  pass "MCP integration prereq"
else
  fail "MCP integration prereq"
fi

check_contains \
  "Python model example" \
  "oc exec -n '${WORKSHOP_NAMESPACE}' '${BACKEND_POD}' -- sh -lc \"python -c 'import json,urllib.request;url=\\\"${MODEL_BASE_URL}/chat/completions\\\";payload={\\\"model\\\":\\\"${MODEL_NAME}\\\",\\\"messages\\\":[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"Say hello in one sentence.\\\"}],\\\"max_tokens\\\":32};req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={\\\"Content-Type\\\":\\\"application/json\\\",\\\"Authorization\\\":\\\"Bearer dummy\\\"},method=\\\"POST\\\");resp=urllib.request.urlopen(req, timeout=120);print(resp.read().decode())'\"" \
  '"choices"'

check_contains \
  "Python app example" \
  "oc exec -n '${WORKSHOP_NAMESPACE}' '${BACKEND_POD}' -- sh -lc \"python -c 'import json,urllib.request;payload={\\\"message\\\":\\\"I am going to Rome next week with cabin baggage only. Check the weather and tell me if I can take a 150 ml bottle and a power bank.\\\",\\\"traveler_profile\\\":{\\\"trip_type\\\":\\\"leisure\\\",\\\"baggage_type\\\":\\\"cabin\\\",\\\"activities\\\":[\\\"walking\\\",\\\"museum\\\"]}};req=urllib.request.Request(\\\"http://localhost:8080/api/v1/chat\\\",data=json.dumps(payload).encode(),headers={\\\"Content-Type\\\":\\\"application/json\\\"},method=\\\"POST\\\");resp=urllib.request.urlopen(req, timeout=180);print(resp.read().decode())'\"" \
  '"destination"'

STREAM_SMOKE_OUTPUT="$(mktemp)"
if curl -sS -N -m 240 -X POST \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  "https://${FRONTEND_ROUTE}/api/v1/chat/stream" \
  -d '{"message":"I am going to Rome next week with cabin baggage only. Check the weather and tell me if I can take a 150 ml bottle and a power bank."}' \
  >"${STREAM_SMOKE_OUTPUT}" 2>/dev/null && grep -q '^event: completed' "${STREAM_SMOKE_OUTPUT}"; then
  pass "Packmate stream smoke"
else
  fail "Packmate stream smoke"
fi
rm -f "${STREAM_SMOKE_OUTPUT}"

if oc -n "${WORKSHOP_NAMESPACE}" exec "${BACKEND_POD}" -- sh -lc \
  "cd /app && PYTHONPATH=/app python evals/runner.py --mode deterministic --threshold 0.90" \
  >/tmp/packmate-eval.txt 2>&1; then
  pass "Evaluation"
else
  fail "Evaluation"
fi

[[ -f "${ROOT}/workshop/PARTICIPANT_GUIDE.md" && -f "${ROOT}/workshop/INSTRUCTOR_GUIDE.md" && -f "${ROOT}/workshop/ARCHITECTURE.md" && -f "${ROOT}/workshop/TROUBLESHOOTING.md" ]] && pass "Documentation" || fail "Documentation"
if compgen -G "${ROOT}/workshop/images/*.png" >/dev/null; then
  pass "Screenshots"
else
  fail "Screenshots"
fi
if packmate_secret_scan "${ROOT}" >/tmp/packmate-secret-scan.txt 2>&1; then
  pass "Secret scan"
else
  fail "Secret scan"
fi

printf '\n'
if [[ "${FAIL_COUNT}" -gt 0 ]]; then
  printf 'WORKSHOP NOT READY (%s failed checks)\n' "${FAIL_COUNT}"
  exit 1
fi
printf 'WORKSHOP READY\n'
