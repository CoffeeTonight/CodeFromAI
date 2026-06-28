#!/usr/bin/env bash
# goal_build_id = 12 — canonical self-harness gate
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAX_TIER="${SOCVERIF_MAX_TIER:-2}"
export SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH" "$ROOT/.socverif/scratch/selftest"
cd "$ROOT"

python3 -m socverif.cli loop . --max-tier "$MAX_TIER" 2>&1 | tee "$SCRATCH/self_harness_loop.log"
TOY_REPEAT="${SOCVERIF_TOY_LOOP_REPEAT:-3}"
for ti in $(seq 1 "$TOY_REPEAT"); do
  echo "=== toy_mimic_soc loop repeat $ti/$TOY_REPEAT ===" | tee -a "$SCRATCH/self_harness_loop.log"
  python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier "$MAX_TIER" 2>&1 | tee -a "$SCRATCH/self_harness_loop.log"
  python3 -c "
import json
r=json.load(open('envs/toy_mimic_soc/verif_report.json'))
assert r['all_passed'] and r['tiers_run']==r['tiers_to_run']
print('toy_mimic_repeat_ok', $ti, r['tiers_run'])
" | tee -a "$SCRATCH/self_harness_loop.log"
done
python3 -m socverif.verify_report . --require-self-harness 2>&1 | tee "$SCRATCH/verify_report.log"
echo "ALL VERIFY GOAL STEPS DONE" | tee "$SCRATCH/VERIFY_DONE.log"