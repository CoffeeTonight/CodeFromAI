#!/usr/bin/env bash
# Step 3 — Simulation slave R/W (single / burst / cpu_sync)
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="Simulation slave R/W (single / burst / cpu_sync)"
STEP="03"
RUN_DIR_SUFFIX="03_simulation_slave_R_W_single_burst_cpu_sync"

source "$(dirname "$0")/_run_gate.sh"

require_cmd python3
init_run_dir "${RUN_DIR_SUFFIX}"

run_gate "${VERIFICATION_TITLE}" \
  python3 "${PROJECT_DIR}/ops/simulation/slave_rw.py" \
    --project "${PROJECT_DIR}" \
    --run-dir "${RUN_DIR}"

log "log: ${RUN_DIR}/slave_rw.log"
show_verdict "${RUN_DIR}/verdict_slave_rw.json"