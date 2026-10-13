#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"
packmate_assert_rhoai_35
packmate_ensure_ogx_ready

bash "${ROOT}/scripts/preflight.sh"
bash "${ROOT}/scripts/prepare-workshop.sh"
bash "${ROOT}/scripts/verify-workshop.sh"
