#!/usr/bin/env bash
# goal_build_id = 12 — repeat acquire until capability checklist passes (OBJECTIVE: until)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch/until}"
# SOCVERIF_UNTIL_MAX=0 → unlimited until PASS (safety: SOCVERIF_UNTIL_WALL_SEC)
MAX_ATTEMPTS="${SOCVERIF_UNTIL_MAX:-0}"
WALL_SEC="${SOCVERIF_UNTIL_WALL_SEC:-3600}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH"
cd "$ROOT"

START_EPOCH=$(date +%s)
attempt=0
while true; do
  if [[ "$MAX_ATTEMPTS" != "0" && "$attempt" -ge "$MAX_ATTEMPTS" ]]; then
    break
  fi
  NOW=$(date +%s)
  ELAPSED=$((NOW - START_EPOCH))
  if [[ "$ELAPSED" -ge "$WALL_SEC" ]]; then
    echo "SELF_HARNESS_UNTIL_FAIL reason=wall_sec wall_sec=$WALL_SEC attempts=$attempt" \
      | tee "$SCRATCH/SELF_HARNESS_UNTIL_DONE.log"
    exit 1
  fi
  attempt=$((attempt + 1))
  if [[ "$MAX_ATTEMPTS" == "0" ]]; then
    echo "=== self_harness_until attempt $attempt (unlimited, wall=${WALL_SEC}s) ===" | tee -a "$SCRATCH/until.log"
  else
    echo "=== self_harness_until attempt $attempt/$MAX_ATTEMPTS ===" | tee -a "$SCRATCH/until.log"
  fi
  if SCRATCH="$SCRATCH/attempt_${attempt}" bash "$ROOT/scripts/self_harness_acquire.sh" 2>&1 | tee -a "$SCRATCH/until.log"; then
    echo "SELF_HARNESS_UNTIL_PASS attempts=$attempt elapsed_sec=$ELAPSED" | tee "$SCRATCH/SELF_HARNESS_UNTIL_DONE.log"
    exit 0
  fi
  echo "[until] attempt $attempt FAIL — retry after failed_flow.md review" | tee -a "$SCRATCH/until.log"
done
echo "SELF_HARNESS_UNTIL_FAIL max_attempts=$MAX_ATTEMPTS attempts=$attempt" | tee "$SCRATCH/SELF_HARNESS_UNTIL_DONE.log"
exit 1