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
DSC_NAME="$(packmate_detect_dsc_name)"
OGX_SPEC_STATE="$(oc get datasciencecluster "${DSC_NAME}" -o jsonpath='{.spec.components.ogx.managementState}' 2>/dev/null || true)"
OGX_READY_STATUS="$(oc get datasciencecluster "${DSC_NAME}" -o jsonpath='{.status.conditions[?(@.type=="OGXReady")].status}' 2>/dev/null || true)"
LLAMASTACK_SPEC_STATE="$(oc get datasciencecluster "${DSC_NAME}" -o jsonpath='{.spec.components.llamastackoperator.managementState}' 2>/dev/null || true)"
check "OpenShift 4.20" test "${OPENSHIFT_VERSION#4.20}" != "${OPENSHIFT_VERSION}"
check "OpenShift AI 3.5" test "${RHOAI_VERSION#3.5}" != "${RHOAI_VERSION}"
check "DataScienceCluster" bash -c '[[ -n "'"${DSC_NAME}"'" ]]'
check "Gen AI Studio" bash -c '[[ "$(oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath="{.spec.dashboardConfig.genAiStudio}")" == "true" ]]'
check "Playground UI" bash -c 'oc get deployment gen-ai-ui -n redhat-ods-applications >/dev/null'
check "OGX managed" bash -c '[[ "'"${OGX_SPEC_STATE}"'" == "Managed" ]]'
check "OGX ready" bash -c '[[ "'"${OGX_READY_STATUS}"'" == "True" ]]'
check "Workbench component" bash -c '[[ "$(oc get datasciencecluster "'"${DSC_NAME}"'" -o jsonpath="{.status.components.workbenches.managementState}")" == "Managed" ]]'
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
check "Code Server image stream" bash -c 'oc get is -n redhat-ods-applications code-server-notebook >/dev/null'

note "Validated on" "OpenShift 4.20.38 / RHOAI 3.5.1"
note "DataScienceCluster" "${DSC_NAME}"
note "Shared model" "${MODEL_NAME} in ${MODEL_NAMESPACE}"
note "Model base URL" "${MODEL_BASE_URL}"

printf '\n'
if [[ "${FAILED}" -gt 0 ]]; then
  if [[ "${OGX_SPEC_STATE}" != "Managed" || "${OGX_READY_STATUS}" != "True" ]]; then
    note "Recovery action" "Enable OGX for Playground: oc patch datasciencecluster ${DSC_NAME} --type=merge -p '{\"spec\":{\"components\":{\"ogx\":{\"managementState\":\"Managed\"}}}}'"
    if [[ "${LLAMASTACK_SPEC_STATE}" == "Managed" ]]; then
      note "Recovery action" "If OGX provisioning fails with a LlamaStackOperator deprecation error, also run: oc patch datasciencecluster ${DSC_NAME} --type=merge -p '{\"spec\":{\"components\":{\"llamastackoperator\":{\"managementState\":\"Removed\"}}}}'"
    fi
  fi
  printf 'PREFLIGHT FAILED\n'
  exit 1
fi
printf 'PREFLIGHT PASSED\n'
