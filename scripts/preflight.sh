#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"
packmate_discover_model_url
packmate_write_local_config "${ROOT}"

pass() { printf '%-30s PASS\n' "$1"; }
fail() { printf '%-30s FAIL\n' "$1"; }
note() { printf '%-30s %s\n' "$1" "$2"; }

FAILED=0
check() {
  local label="$1"
  shift
  if "$@"; then
    pass "${label}"
  else
    fail "${label}"
    FAILED=$((FAILED + 1))
  fi
}

printf 'PACKMATE WORKSHOP PREFLIGHT\n'
printf '===========================\n\n'

check "OpenShift authentication" bash -c 'oc whoami >/dev/null'
check "Human identity" bash -c '[[ "$(oc whoami)" != system:serviceaccount:* ]]'
OPENSHIFT_VERSION="$(packmate_detect_openshift_version)"
RHOAI_VERSION="$(packmate_detect_rhoai_version)"
check "OpenShift 4.20" test "${OPENSHIFT_VERSION#4.20}" != "${OPENSHIFT_VERSION}"
check "OpenShift AI 3.5" test "${RHOAI_VERSION#3.5}" != "${RHOAI_VERSION}"
check "DataScienceCluster" bash -c 'oc get datasciencecluster default-dsc -n redhat-ods-applications >/dev/null'
check "Gen AI Studio" bash -c '[[ "$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath="{.spec.dashboardConfig.genAiStudio}")" == "true" ]]'
check "Playground UI" bash -c 'oc get deployment gen-ai-ui -n redhat-ods-applications >/dev/null'
check "Workbench component" bash -c '[[ "$(oc get datasciencecluster default-dsc -n redhat-ods-applications -o jsonpath="{.status.components.workbenches.managementState}")" == "Managed" ]]'
check "Shared Llama" bash -c 'oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" >/dev/null'
check "Model Ready" bash -c '[[ "$(oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" -o jsonpath="{.status.conditions[?(@.type==\"Ready\")].status}")" == "True" ]]'
check "Model endpoint" bash -c '[[ -n "${MODEL_BASE_URL}" ]]'
if packmate_model_auth_enabled; then
  fail "Model auth disabled"
  FAILED=$((FAILED + 1))
else
  pass "Model auth disabled"
fi
check "Serving runtime" oc get servingruntime "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" >/dev/null
check "KServe runtime path" bash -c 'oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" -o jsonpath="{.spec.predictor.model.runtime}" | grep -q .'
check "MCP config namespace" bash -c 'oc get namespace "${MCP_CONFIG_NAMESPACE}" >/dev/null'
check "MCP ConfigMap writable" bash -c 'oc auth can-i create configmaps -n "${MCP_CONFIG_NAMESPACE}" >/dev/null'
check "Workshop namespace rights" bash -c 'oc auth can-i create deployments -n "${WORKSHOP_NAMESPACE}" >/dev/null'
check "Route/DNS" bash -c 'oc get route data-science-gateway -n redhat-ods-applications >/dev/null'
check "Workbench image stream" bash -c 'oc get is -n redhat-ods-applications s2i-generic-data-science-notebook >/dev/null'

note "Validated on" "OpenShift 4.20.38 / RHOAI 3.5.1"
note "Shared model" "${MODEL_NAME} in ${MODEL_NAMESPACE}"
note "Model base URL" "${MODEL_BASE_URL}"

printf '\n'
if [[ "${FAILED}" -gt 0 ]]; then
  printf 'PREFLIGHT FAILED\n'
  exit 1
fi
printf 'PREFLIGHT PASSED\n'
