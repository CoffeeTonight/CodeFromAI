#!/usr/bin/env bash
# After verification sequence — regenerate reports/by_tag/{tag}/
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="Generate verification reports (from reports/index.yaml)"
STEP="99"

require_cmd python3
log "${VERIFICATION_TITLE}"

REPORT_ARGS=(--project "${PROJECT_DIR}")
if [[ -n "${RUN_ID:-}" ]]; then
  REPORT_ARGS+=(--run-id "${RUN_ID}")
fi

run_gate "${VERIFICATION_TITLE}" \
  python3 "${PROJECT_DIR}/ops/report/generate_reports.py" \
    "${REPORT_ARGS[@]}"

log "summary: ${PROJECT_DIR}/reports/by_tag/${TAG}/SUMMARY.md"