#!/usr/bin/env bash
# goal_build_id = 12 — thin wrapper; predicates live in socverif.capability_gate
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACQUIRE_SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch/acquire}"
REQUIRED_STREAK="${SOCVERIF_REQUIRED_STREAK:-3}"
MAX_ROUNDS="${SOCVERIF_MAX_ROUNDS:-7}"
MAX_TIER="${SOCVERIF_MAX_TIER:-2}"
TOY_REPEAT="${SOCVERIF_TOY_LOOP_REPEAT:-3}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$ACQUIRE_SCRATCH"
cd "$ROOT"

echo "=== self_harness_acquire streak_target=$REQUIRED_STREAK toy_repeat=$TOY_REPEAT ===" | tee "$ACQUIRE_SCRATCH/acquire.log"

export SOCVERIF_REQUIRED_STREAK="$REQUIRED_STREAK"
export SOCVERIF_MAX_ROUNDS="$MAX_ROUNDS"
export SOCVERIF_MAX_TIER="$MAX_TIER"
export SOCVERIF_TOY_LOOP_REPEAT="$TOY_REPEAT"
SCRATCH="$ACQUIRE_SCRATCH/repeat" bash "$ROOT/scripts/self_harness_repeat.sh" 2>&1 | tee -a "$ACQUIRE_SCRATCH/acquire.log"
grep -q "SELF_HARNESS_REPEAT_PASS streak=$REQUIRED_STREAK" "$ACQUIRE_SCRATCH/acquire.log"

echo "=== capability probe ===" | tee -a "$ACQUIRE_SCRATCH/acquire.log"
python3 -m socverif.capability_gate probe-toy --env envs/toy_mimic_soc --max-tier "$MAX_TIER" \
  2>&1 | tee "$ACQUIRE_SCRATCH/capability_probe.json"

echo "=== toy-create E2E ===" | tee -a "$ACQUIRE_SCRATCH/acquire.log"
mkdir -p "$ACQUIRE_SCRATCH/toys"
python3 -m socverif.cli toy-create envs/minimal_soc --name acquire_toy --out-dir "$ACQUIRE_SCRATCH/toys" --force \
  2>&1 | tee "$ACQUIRE_SCRATCH/toy_create.log"
python3 -m socverif.cli loop "$ACQUIRE_SCRATCH/toys/acquire_toy" --max-tier "$MAX_TIER" \
  2>&1 | tee "$ACQUIRE_SCRATCH/toy_created_loop.log"

python3 -m socverif.capability_gate evaluate-acquire \
  --streak "$REQUIRED_STREAK" \
  --rounds "$REQUIRED_STREAK" \
  --probe-json "$ACQUIRE_SCRATCH/capability_probe.json" \
  --toy-report "$ACQUIRE_SCRATCH/toys/acquire_toy/verif_report.json" \
  --toy-tier2-log "$ACQUIRE_SCRATCH/toys/acquire_toy/sim_logs/tier2.log" \
  --required-streak "$REQUIRED_STREAK" \
  --toy-repeat "$TOY_REPEAT" \
  2>&1 | tee "$ACQUIRE_SCRATCH/capability_acquire_eval.json"

python3 -c "
import json
from pathlib import Path
r = json.loads(Path('${ACQUIRE_SCRATCH}/capability_acquire_eval.json').read_text())
assert r['ok'], r
print(r['message'])
" | tee "$ACQUIRE_SCRATCH/SELF_HARNESS_CAPABILITY_ACQUIRED.log"