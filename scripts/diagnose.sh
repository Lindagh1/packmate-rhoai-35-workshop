#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"

printf 'PACKMATE WORKSHOP DIAGNOSE\n'
printf '==========================\n\n'

printf 'Current user: %s\n' "$(oc whoami)"
printf 'OpenShift: %s\n' "$(packmate_detect_openshift_version)"
printf 'OpenShift AI: %s\n\n' "$(packmate_detect_rhoai_version)"

if [[ "$(oc whoami)" == system:serviceaccount:* ]]; then
  printf 'SYMPTOM: authenticated as a ServiceAccount\n'
  printf 'RECOVERY: run oc logout and authenticate as a human user\n\n'
fi

if ! oc get namespace "${WORKSHOP_NAMESPACE}" >/dev/null 2>&1; then
  printf 'SYMPTOM: workshop namespace %s missing\n' "${WORKSHOP_NAMESPACE}"
  printf 'RECOVERY: run make prepare-workshop\n\n'
fi

ready="$(oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
if [[ "${ready}" != "True" ]]; then
  printf 'SYMPTOM: shared model is not Ready\n'
  printf 'HOW TO CHECK: oc get inferenceservice %s -n %s -o yaml\n' "${MODEL_NAME}" "${MODEL_NAMESPACE}"
  printf 'RECOVERY: wait for the shared platform model to recover; do not redeploy it from this workshop\n\n'
fi

if ! oc get configmap gen-ai-aa-mcp-servers -n "${MCP_CONFIG_NAMESPACE}" >/dev/null 2>&1; then
  printf 'SYMPTOM: Playground MCP registration missing\n'
  printf 'HOW TO CHECK: oc get configmap gen-ai-aa-mcp-servers -n %s\n' "${MCP_CONFIG_NAMESPACE}"
  printf 'RECOVERY: run make prepare-workshop\n\n'
fi

for deploy in weather-mcp baggage-policy-mcp packmate-backend packmate-frontend; do
  if ! oc -n "${WORKSHOP_NAMESPACE}" rollout status "deploy/${deploy}" --timeout=5s >/dev/null 2>&1; then
    printf 'SYMPTOM: deployment %s is not ready\n' "${deploy}"
    printf 'HOW TO CHECK: oc get pods -n %s -l app=%s\n' "${WORKSHOP_NAMESPACE}" "${deploy}"
    printf 'RECOVERY: oc describe deploy/%s -n %s and inspect pod logs\n\n' "${deploy}" "${WORKSHOP_NAMESPACE}"
  fi
done

frontend_route="$(oc -n "${WORKSHOP_NAMESPACE}" get route packmate-frontend -o jsonpath='{.spec.host}' 2>/dev/null || true)"
if [[ -n "${frontend_route}" ]]; then
  code="$(curl -sk -o /dev/null -w '%{http_code}' -m 20 "https://${frontend_route}/" || echo 000)"
  if [[ "${code}" != "200" ]]; then
    printf 'SYMPTOM: frontend route returned HTTP %s\n' "${code}"
    printf 'RECOVERY: check router, service, and frontend pod readiness\n\n'
  fi
fi
