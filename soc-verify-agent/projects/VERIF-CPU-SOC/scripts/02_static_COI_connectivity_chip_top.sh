#!/usr/bin/env bash
# Step 2 — Static COI connectivity (chip_top)
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="Static COI connectivity (chip_top)"
STEP="02"
RUN_DIR_SUFFIX="02_static_COI_connectivity_chip_top"

source "$(dirname "$0")/_run_gate.sh"

require_cmd python3

if ! command -v hier-walk >/dev/null 2>&1; then
  HIERWALK_SRC="${HIERWALK_PATH:-}"
  if [[ -z "$HIERWALK_SRC" ]]; then
    for candidate in "${HOME}/tools/hierwalk" /home/user/tools/hierwalk "${HOME}/tools/__CFI/hierwalk" "${HOME}/tools/__CFA/hierwalk" /home/user/tools/__CFI/hierwalk /home/user/tools/__CFA/hierwalk /home/user/Desktop/hierwalk; do
      if [[ -d "$candidate" ]]; then
        HIERWALK_SRC="$candidate"
        break
      fi
    done
  fi
  if [[ -n "$HIERWALK_SRC" && -d "$HIERWALK_SRC" ]]; then
    log "installing hierwalk from ${HIERWALK_SRC} (editable)..."
    python3 -m pip install -e "$HIERWALK_SRC" -q
  else
    die "hier-walk not found; set HIERWALK_PATH or pip install -e <path/to/hierwalk>"
  fi
fi

INTAKE="${PROJECT_DIR}/inputs/tags/${TAG}/deployment/customer_soc_intake.yaml"
if [[ -f "${INTAKE}" ]]; then
  log "crystallize gate overrides from intake (coi_conn + slave_rw)"
  python3 "${PROJECT_DIR}/scripts/crystallize_gate_from_intake.py" --project "${PROJECT_DIR}" --tag "${TAG}"
fi

init_run_dir "${RUN_DIR_SUFFIX}"

OVERRIDE="${PROJECT_DIR}/inputs/tags/${TAG}/overrides/coi_conn_checks.json"
if [[ -f "${OVERRIDE}" ]]; then
  log "override checks -> ${RUN_DIR}/coi_conn_checks.json"
  cp "${OVERRIDE}" "${RUN_DIR}/coi_conn_checks.json"
fi

log "parallel: coi_hierarchy (producer) + coi_conn (consumer)"
python3 "${PROJECT_DIR}/ops/static/coi_hierarchy.py" \
  --project "${PROJECT_DIR}" \
  --run-dir "${RUN_DIR}" &
HIER_PID=$!
python3 "${PROJECT_DIR}/ops/static/coi_conn.py" \
  --project "${PROJECT_DIR}" \
  --run-dir "${RUN_DIR}" &
CONN_PID=$!

HIER_RC=0
CONN_RC=0
wait "${HIER_PID}" || HIER_RC=$?
wait "${CONN_PID}" || CONN_RC=$?

log "hierarchy verdict:"
show_verdict "${RUN_DIR}/verdict_coi_hierarchy.json" || true
log "conn verdict:"
show_verdict "${RUN_DIR}/verdict_coi_conn.json" || true
log "tsv: ${RUN_DIR}/coi_conn.tsv"

if [[ "${HIER_RC}" -ne 0 || "${CONN_RC}" -ne 0 ]]; then
  die "coi pipeline failed (hierarchy=${HIER_RC} conn=${CONN_RC})"
fi