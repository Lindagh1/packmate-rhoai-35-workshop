#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"

printf 'Resetting participant-facing workshop resources in %s\n' "${WORKSHOP_NAMESPACE}"

oc -n "${WORKSHOP_NAMESPACE}" rollout restart deploy/weather-mcp deploy/baggage-policy-mcp deploy/packmate-backend deploy/packmate-frontend >/dev/null 2>&1 || true
oc -n "${WORKSHOP_NAMESPACE}" delete pod -l app=weather-mcp --ignore-not-found --wait=false >/dev/null 2>&1 || true
oc -n "${WORKSHOP_NAMESPACE}" delete pod -l app=baggage-policy-mcp --ignore-not-found --wait=false >/dev/null 2>&1 || true
oc -n "${WORKSHOP_NAMESPACE}" delete pod -l app=packmate-backend --ignore-not-found --wait=false >/dev/null 2>&1 || true
oc -n "${WORKSHOP_NAMESPACE}" delete pod -l app=packmate-frontend --ignore-not-found --wait=false >/dev/null 2>&1 || true

oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/weather-mcp --timeout=10m
oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/baggage-policy-mcp --timeout=10m
oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/packmate-backend --timeout=10m
oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/packmate-frontend --timeout=10m

printf 'Participant reset complete\n'
