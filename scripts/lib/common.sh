#!/usr/bin/env bash
set -euo pipefail

packmate_root() {
  cd "$(dirname "${BASH_SOURCE[1]}")/../.." && pwd
}

packmate_config_path() {
  local root="${1:-$(packmate_root)}"
  printf '%s/config/workshop.env\n' "${root}"
}

packmate_log() { printf '%s\n' "$*"; }
packmate_die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

packmate_require_oc() {
  command -v oc >/dev/null 2>&1 || packmate_die "oc CLI not found"
}

packmate_require_auth() {
  packmate_require_oc
  oc whoami >/dev/null 2>&1 || packmate_die "OpenShift authentication missing. Run oc login first."
}

packmate_load_or_default_config() {
  local root="${1:-$(packmate_root)}"
  local cfg
  cfg="$(packmate_config_path "${root}")"
  if [[ -f "${cfg}" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "${cfg}"
    set +a
  fi
  WORKSHOP_NAMESPACE="${WORKSHOP_NAMESPACE:-packmate-lab}"
  MODEL_NAMESPACE="${MODEL_NAMESPACE:-my-first-model}"
  MODEL_NAME="${MODEL_NAME:-llama-32-3b-instruct}"
  MODEL_SERVICE="${MODEL_SERVICE:-llama-32-3b-instruct-predictor}"
  MCP_CONFIG_NAMESPACE="${MCP_CONFIG_NAMESPACE:-redhat-ods-applications}"
  WORKSHOP_MANAGED_LABEL="${WORKSHOP_MANAGED_LABEL:-workshop.packmate/managed=true}"
  WORKSHOP_PART_OF_LABEL="${WORKSHOP_PART_OF_LABEL:-app.kubernetes.io/part-of=packmate-workshop}"
  MODEL_BASE_URL="${MODEL_BASE_URL:-}"
  export WORKSHOP_NAMESPACE MODEL_NAMESPACE MODEL_NAME MODEL_SERVICE MCP_CONFIG_NAMESPACE
  export WORKSHOP_MANAGED_LABEL WORKSHOP_PART_OF_LABEL MODEL_BASE_URL
}

packmate_detect_openshift_version() {
  oc get clusterversion version -o jsonpath='{.status.desired.version}'
}

packmate_detect_dsc_name() {
  oc get datasciencecluster -o jsonpath='{.items[0].metadata.name}'
}

packmate_detect_rhoai_version() {
  local dsc_name
  dsc_name="$(packmate_detect_dsc_name)"
  oc get datasciencecluster "${dsc_name}" -o jsonpath='{.status.release.version}'
}

packmate_assert_rhoai_35() {
  local version
  version="$(packmate_detect_rhoai_version)"
  [[ "${version}" == 3.5* ]] || packmate_die "Expected Red Hat OpenShift AI 3.5.x, got ${version}"
}

packmate_detect_ogx_spec_state() {
  local dsc_name="${1:-$(packmate_detect_dsc_name)}"
  oc get datasciencecluster "${dsc_name}" -o jsonpath='{.spec.components.ogx.managementState}' 2>/dev/null || true
}

packmate_detect_ogx_ready_status() {
  local dsc_name="${1:-$(packmate_detect_dsc_name)}"
  oc get datasciencecluster "${dsc_name}" -o jsonpath='{.status.conditions[?(@.type=="OGXReady")].status}' 2>/dev/null || true
}

packmate_detect_llamastack_spec_state() {
  local dsc_name="${1:-$(packmate_detect_dsc_name)}"
  oc get datasciencecluster "${dsc_name}" -o jsonpath='{.spec.components.llamastackoperator.managementState}' 2>/dev/null || true
}

packmate_wait_for_ogx_ready() {
  local dsc_name="${1:-$(packmate_detect_dsc_name)}"
  local timeout_seconds="${2:-600}"
  local sleep_seconds="${3:-15}"
  local waited=0

  while (( waited <= timeout_seconds )); do
    local ogx_ready
    ogx_ready="$(packmate_detect_ogx_ready_status "${dsc_name}")"
    if [[ "${ogx_ready}" == "True" ]]; then
      return 0
    fi

    local ogx_reason
    ogx_reason="$(oc get datasciencecluster "${dsc_name}" -o jsonpath='{.status.conditions[?(@.type=="OGXReady")].reason}' 2>/dev/null || true)"
    packmate_log "Waiting for OGX to become ready on ${dsc_name} (${ogx_ready:-Unknown}/${ogx_reason:-Unknown})..."
    sleep "${sleep_seconds}"
    waited=$((waited + sleep_seconds))
  done

  return 1
}

packmate_ensure_ogx_ready() {
  local dsc_name
  dsc_name="$(packmate_detect_dsc_name)"

  [[ -n "${dsc_name}" ]] || packmate_die "No DataScienceCluster found."

  local ogx_spec_state ogx_ready_status lso_spec_state
  ogx_spec_state="$(packmate_detect_ogx_spec_state "${dsc_name}")"
  ogx_ready_status="$(packmate_detect_ogx_ready_status "${dsc_name}")"
  lso_spec_state="$(packmate_detect_llamastack_spec_state "${dsc_name}")"

  if [[ "${ogx_spec_state}" == "Managed" && "${ogx_ready_status}" == "True" ]]; then
    packmate_log "OGX is already ready on ${dsc_name}."
    return 0
  fi

  oc auth can-i patch datascienceclusters.datasciencecluster.opendatahub.io >/dev/null 2>&1 || \
    packmate_die "Missing permission to patch DataScienceCluster ${dsc_name}. Run with a cluster-admin capable identity."

  if [[ "${ogx_spec_state}" != "Managed" ]]; then
    packmate_log "Enabling OGX on ${dsc_name}."
    oc patch datasciencecluster "${dsc_name}" --type=merge -p '{"spec":{"components":{"ogx":{"managementState":"Managed"}}}}' >/dev/null
  fi

  if [[ "${ogx_ready_status}" != "True" && "${lso_spec_state}" == "Managed" ]]; then
    packmate_log "Removing legacy Llama Stack operator component on ${dsc_name} to allow OGX rollout."
    oc patch datasciencecluster "${dsc_name}" --type=merge -p '{"spec":{"components":{"llamastackoperator":{"managementState":"Removed"}}}}' >/dev/null
  fi

  if ! packmate_wait_for_ogx_ready "${dsc_name}"; then
    packmate_die "OGX did not become ready on ${dsc_name}. Run 'make preflight' for the latest status."
  fi

  packmate_log "OGX is ready on ${dsc_name}."
}

packmate_route_domain() {
  oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}'
}

packmate_discover_model_url() {
  local svc_port target cluster_ip
  svc_port="$(oc get svc "${MODEL_SERVICE}" -n "${MODEL_NAMESPACE}" -o jsonpath='{.spec.ports[0].port}')"
  target="$(oc get svc "${MODEL_SERVICE}" -n "${MODEL_NAMESPACE}" -o jsonpath='{.spec.ports[0].targetPort}')"
  cluster_ip="$(oc get svc "${MODEL_SERVICE}" -n "${MODEL_NAMESPACE}" -o jsonpath='{.spec.clusterIP}')"
  local probe_port="${svc_port}"
  if [[ "${cluster_ip}" == "None" || -z "${cluster_ip}" ]]; then
    probe_port="${target}"
  fi
  MODEL_BASE_URL="http://${MODEL_SERVICE}.${MODEL_NAMESPACE}.svc.cluster.local:${probe_port}/v1"
  export MODEL_BASE_URL
}

packmate_model_auth_enabled() {
  local enabled
  enabled="$(oc get inferenceservice "${MODEL_NAME}" -n "${MODEL_NAMESPACE}" -o jsonpath='{.metadata.annotations.security\.opendatahub\.io/enable-auth}' 2>/dev/null || true)"
  [[ "${enabled}" == "true" ]]
}

packmate_write_local_config() {
  local root="${1:-$(packmate_root)}"
  local cfg
  cfg="$(packmate_config_path "${root}")"
  mkdir -p "$(dirname "${cfg}")"
  cat > "${cfg}" <<EOF
WORKSHOP_NAMESPACE=${WORKSHOP_NAMESPACE}
MODEL_NAMESPACE=${MODEL_NAMESPACE}
MODEL_NAME=${MODEL_NAME}
MODEL_SERVICE=${MODEL_SERVICE}
MODEL_BASE_URL=${MODEL_BASE_URL}
MCP_CONFIG_NAMESPACE=${MCP_CONFIG_NAMESPACE}
WORKSHOP_MANAGED_LABEL=${WORKSHOP_MANAGED_LABEL}
WORKSHOP_PART_OF_LABEL=${WORKSHOP_PART_OF_LABEL}
EOF
}

packmate_managed_labels() {
  printf '%s\n%s\n' "${WORKSHOP_PART_OF_LABEL}" "${WORKSHOP_MANAGED_LABEL}"
}

packmate_namespace_exists() {
  oc get namespace "${WORKSHOP_NAMESPACE}" >/dev/null 2>&1
}

packmate_apply_namespace() {
  oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${WORKSHOP_NAMESPACE}
  labels:
    ${WORKSHOP_PART_OF_LABEL%%=*}: "${WORKSHOP_PART_OF_LABEL#*=}"
    ${WORKSHOP_MANAGED_LABEL%%=*}: "${WORKSHOP_MANAGED_LABEL#*=}"
    opendatahub.io/dashboard: "true"
EOF
}

packmate_secret_scan() {
  local root="${1:-$(packmate_root)}"
  local patterns='sha256~[A-Za-z0-9._-]+|github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]+|-----BEGIN[[:space:]][A-Z ]+PRIVATE KEY-----|([Pp]ASSWORD|[Tt][Oo][Kk][Ee][Nn]|[Ss][Ee][Cc][Rr][Ee][Tt]|api[_-]?key)[[:space:]]*[:=][[:space:]]*["'"'"'"][^"'"'"'[:space:]]{8,}["'"'"'"]'
  ! rg -n -i \
    --glob '!workshop/images/**' \
    --glob '!app/frontend/package-lock.json' \
    --glob '!app/backend/tests/**' \
    --glob '!mcp/**/tests/**' \
    --glob '!.git/**' \
    "${patterns}" "${root}"
}
