# shellcheck shell=bash
# Helpers for numbered verification scripts (source after _common.sh).

init_run_dir() {
  local suffix="$1"
  if [[ -z "${RUN_ID:-}" ]]; then
    export RUN_ID="${RUN_ID_PREFIX:-verify-${TAG}}-${suffix}"
  fi
  export RUN_DIR="${PROJECT_DIR}/runs/${RUN_ID}"
  mkdir -p "${RUN_DIR}"
  log "verification: ${VERIFICATION_TITLE:-?}"
  log "step: ${STEP:-?}"
  log "project: ${PROJECT_DIR}"
  log "run_dir: ${RUN_DIR}"
}

show_verdict() {
  local path="$1"
  log "verdict: ${path}"
  python3 -c "import json; v=json.load(open('${path}')); print('status:', v['status'])"
}