#!/usr/bin/env bash
# After verification sequence — regenerate reports/by_tag/{tag}/
set -euo pipefail
source "$(dirname "$0")/_common.sh"

VERIFICATION_TITLE="Generate verification reports (from reports/index.yaml)"
STEP="99"

require_cmd python3
log "${VERIFICATION_TITLE}"

run_gate "${VERIFICATION_TITLE}" \
  python3 "${PROJECT_DIR}/ops/report/generate_reports.py" \
    --project "${PROJECT_DIR}"

log "summary: ${PROJECT_DIR}/reports/by_tag/${TAG}/SUMMARY.md"