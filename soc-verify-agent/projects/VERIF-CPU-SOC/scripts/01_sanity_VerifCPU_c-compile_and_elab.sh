#!/usr/bin/env bash
# Step 1 — Sanity — VerifCPU c-compile & elab
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="Sanity — VerifCPU c-compile & elab"
STEP="01"
RUN_DIR_SUFFIX="01_sanity_VerifCPU_c-compile_and_elab"

# shellcheck disable=SC1091
source "$(dirname "$0")/_run_gate.sh"

require_cmd python3
init_run_dir "${RUN_DIR_SUFFIX}"

run_gate "${VERIFICATION_TITLE}" \
  python3 "${PROJECT_DIR}/ops/sanity/c-compile.py" \
    --project "${PROJECT_DIR}" \
    --run-dir "${RUN_DIR}"

show_verdict "${RUN_DIR}/verdict_c-compile.json"