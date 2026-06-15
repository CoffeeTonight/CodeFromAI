#!/usr/bin/env bash
# Step 2 — Static COI connectivity (chip_top)
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="Static COI connectivity (chip_top)"
STEP="02"
RUN_DIR_SUFFIX="02_static_COI_connectivity_chip_top"

source "$(dirname "$0")/_run_gate.sh"

require_cmd python3

if ! command -v scan-inst >/dev/null 2>&1; then
  if [[ -d /home/user/Desktop/scan_inst ]]; then
    log "installing scan_inst (editable)..."
    python3 -m pip install -e /home/user/Desktop/scan_inst -q
  else
    die "scan-inst not found; pip install -e <path/to/scan_inst>"
  fi
fi

init_run_dir "${RUN_DIR_SUFFIX}"

OVERRIDE="${PROJECT_DIR}/inputs/tags/${TAG}/overrides/coi_conn_checks.json"
if [[ -f "${OVERRIDE}" ]]; then
  log "override checks -> ${RUN_DIR}/coi_conn_checks.json"
  cp "${OVERRIDE}" "${RUN_DIR}/coi_conn_checks.json"
fi

run_gate "${VERIFICATION_TITLE}" \
  python3 "${PROJECT_DIR}/ops/static/coi_conn.py" \
    --project "${PROJECT_DIR}" \
    --run-dir "${RUN_DIR}"

log "tsv: ${RUN_DIR}/coi_conn.tsv"
show_verdict "${RUN_DIR}/verdict_coi_conn.json"