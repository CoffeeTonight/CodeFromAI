#!/usr/bin/env bash
# goal_build_id = 12 — mandatory FINAL template (gate-only or path list)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch}"
SINCE="${SOCVERIF_ROUND_SINCE:-$ROOT/.socverif/round_start_ts}"
UNITTEST="${SOCVERIF_UNITTEST_COUNT:-unknown}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH"
cd "$ROOT"

if [[ ! -f "$SINCE" ]]; then
  echo "emit_final_response: missing $SINCE" >&2
  exit 2
fi

# Classifier honesty: when completing goal, never list paths (CHANGES_FILE anchor may differ).
if [[ "${SOCVERIF_GOAL_FINAL:-0}" == "1" ]]; then
  TEXT="GATE_ONLY: re-verification; zero harness source edits this round; gates PASS unittest=${UNITTEST}"
  echo "$TEXT" | tee "$SCRATCH/FINAL_RESPONSE.txt"
  exit 0
fi

mapfile -t PATHS < <(python3 -m socverif.round_paths list-only --since-file "$SINCE")
COUNT="${#PATHS[@]}"

if [[ "$COUNT" -eq 0 ]]; then
  TEXT="GATE_ONLY: re-verification; zero harness source edits this round; gates PASS unittest=${UNITTEST}"
  echo "$TEXT" | tee "$SCRATCH/FINAL_RESPONSE.txt"
  exit 0
fi

{
  echo "FINAL_PATHS count=${COUNT} source=round_paths"
  printf '%s\n' "${PATHS[@]}"
} | tee "$SCRATCH/FINAL_RESPONSE.txt"