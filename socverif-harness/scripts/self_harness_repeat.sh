#!/usr/bin/env bash
# goal_build_id = 12 — repeat self-harness until N consecutive PASS (반복해)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPEAT_LOG_DIR="$ROOT/.socverif/scratch/repeat"
SCRATCH="${SCRATCH:-$REPEAT_LOG_DIR}"
REQUIRED_STREAK="${SOCVERIF_REQUIRED_STREAK:-3}"
MAX_ROUNDS="${SOCVERIF_MAX_ROUNDS:-7}"
MAX_TIER="${SOCVERIF_MAX_TIER:-2}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$REPEAT_LOG_DIR"
cd "$ROOT"
REPEAT_LOG="$REPEAT_LOG_DIR/repeat.log"

_fresh_self_harness_state() {
  local round="$1"
  local round_scratch="$REPEAT_LOG_DIR/round_${round}_fresh"
  rm -rf "$round_scratch"
  mkdir -p "$round_scratch"
  rm -f "$ROOT/.socverif/scratch/verif_report.json"
  rm -f "$ROOT/.socverif/scratch/environment_manifest.yaml"
  export SCRATCH="$round_scratch"
}

streak=0
round=0
while [ "$round" -lt "$MAX_ROUNDS" ]; do
  round=$((round + 1))
  _fresh_self_harness_state "$round"
  echo "=== self_harness_repeat round $round/$MAX_ROUNDS (streak=$streak/$REQUIRED_STREAK) fresh=$SCRATCH ===" | tee -a "$REPEAT_LOG"
  if SOCVERIF_MAX_TIER="$MAX_TIER" bash "$ROOT/scripts/verify_goal.sh" 2>&1 | tee "$SCRATCH/round_${round}.log"; then
    streak=$((streak + 1))
    echo "[repeat] PASS streak=$streak" | tee -a "$REPEAT_LOG"
    if [ "$streak" -ge "$REQUIRED_STREAK" ]; then
      echo "SELF_HARNESS_REPEAT_PASS streak=$streak rounds=$round" | tee "$SCRATCH/SELF_HARNESS_REPEAT_DONE.log"
      exit 0
    fi
  else
    streak=0
    echo "[repeat] FAIL — streak reset" | tee -a "$REPEAT_LOG"
  fi
done
echo "SELF_HARNESS_REPEAT_FAIL max_rounds=$MAX_ROUNDS" | tee "$SCRATCH/SELF_HARNESS_REPEAT_DONE.log"
exit 1