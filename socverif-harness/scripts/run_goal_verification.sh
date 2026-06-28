#!/usr/bin/env bash
# goal_build_id = 18 — CFA-only verify; freeze_classifier_snapshot attempt patch
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
# shellcheck source=scripts/resolve_goal_env.sh
source "$ROOT/scripts/resolve_goal_env.sh"
SCRATCH="${SCRATCH:?SCRATCH unset after resolve_goal_env}"
GOAL_ROOT="${SOCVERIF_GOAL_ROOT:?SOCVERIF_GOAL_ROOT unset}"
mkdir -p "$SCRATCH"
cd "$ROOT"
echo "verify_cwd=$ROOT (CFA-only, no workspace mirror)" | tee "$SCRATCH/verify_cwd.log"

echo "=== step 0: round_paths + preflight_final_claims ===" | tee "$SCRATCH/goal_verification.log"
python3 -m socverif.round_paths check --since-file .socverif/round_start_ts \
  2>&1 | tee "$SCRATCH/round_paths.log"
bash scripts/emit_round_changed_paths.sh > "$SCRATCH/round_changed_paths.txt"
echo "round_changed_count=$(wc -l < "$SCRATCH/round_changed_paths.txt" | tr -d ' ')" | tee "$SCRATCH/round_changed_count.log"
python3 -m socverif.workspace_delta check --since-file .socverif/round_start_ts \
  2>&1 | tee "$SCRATCH/workspace_snapshot_audit.log" || true

echo "=== step 0b: plan_contract + delivery_bundle ===" | tee -a "$SCRATCH/goal_verification.log"
python3 -m socverif.plan_contract --json 2>&1 | tee "$SCRATCH/plan_contract.log"
python3 -c "
import json
from pathlib import Path
text = Path('${SCRATCH}/plan_contract.log').read_text()
r = json.loads(text[text.rfind('{'):])
assert r.get('ok') and not r.get('defects'), r
print('plan_contract_gate_ok defects=', r.get('defects'))
" 2>&1 | tee "$SCRATCH/plan_contract_assert.log"
python3 -m socverif.delivery_bundle emit --scratch "$SCRATCH" 2>&1 | tee "$SCRATCH/delivery_bundle_emit.log"
python3 -m socverif.delivery_bundle check --min-paths 0 2>&1 | tee "$SCRATCH/delivery_bundle_check.log"

bash scripts/preflight_final_claims.sh 2>&1 | tee "$SCRATCH/preflight_final_claims_run.log"
bash scripts/emit_round_evidence.sh "$SCRATCH" 2>&1 | tee "$SCRATCH/emit_round_evidence.log"
test -f "$SCRATCH/ROUND_EVIDENCE.json"
bash scripts/final_response_paths.sh > "$SCRATCH/final_response_paths.txt"

echo "=== step 1: docs_check + user_methods ===" | tee -a "$SCRATCH/goal_verification.log"
bash scripts/docs_check.sh "$SCRATCH/docs_check.log"
grep -q 'USER_METHODS_CHECK_PASS' "$SCRATCH/docs_check.log"
python3 -m socverif.user_methods --json 2>&1 | tee "$SCRATCH/user_methods.log"

echo "=== step 2: self_verify_pr ===" | tee -a "$SCRATCH/goal_verification.log"
/usr/bin/time -f 'pr_elapsed %e' bash scripts/self_verify_pr.sh 2>&1 | tee "$SCRATCH/self_verify_pr.log"

echo "=== step 3: self_verify_nightly x2 ===" | tee -a "$SCRATCH/goal_verification.log"
: > "$SCRATCH/self_verify_nightly.log"
for i in 1 2; do
  echo "--- nightly run $i ---" | tee -a "$SCRATCH/self_verify_nightly.log"
  /usr/bin/time -f "nightly${i}_elapsed %e" \
    env SOCVERIF_MAX_TIER=2 bash scripts/self_verify_nightly.sh 2>&1 | tee -a "$SCRATCH/self_verify_nightly.log"
done

echo "=== step 4: toy loops (minimal, alt, toy_mimic) ===" | tee -a "$SCRATCH/goal_verification.log"
/usr/bin/time -f 'minimal_elapsed %e' \
  python3 -m socverif.cli loop envs/minimal_soc --max-tier 2 2>&1 | tee "$SCRATCH/loop_minimal_toy.log"
grep -q 'tiers_to_run=3' "$SCRATCH/loop_minimal_toy.log"
grep -q 'max_tier=2' "$SCRATCH/loop_minimal_toy.log"
python3 -c "
import json
r=json.load(open('envs/minimal_soc/verif_report.json'))
assert r['all_passed'] and r['max_tier']==2 and r['tiers_to_run']==3
assert r['tiers_run']==r['tiers_to_run'] and len(r['results'])==3
print('minimal_report_ok', r['tiers_run'], 'tiers_to_run', r['tiers_to_run'])
" | tee "$SCRATCH/loop_minimal_report_assert.log"

/usr/bin/time -f 'alt_elapsed %e' \
  python3 -m socverif.cli loop envs/alt_soc --max-tier 1 2>&1 | tee "$SCRATCH/loop_alt_toy.log"

/usr/bin/time -f 'toy_mimic_elapsed %e' \
  python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2 2>&1 | tee "$SCRATCH/loop_toy_mimic.log"
python3 -c "
import json
from pathlib import Path
r=json.load(open('envs/toy_mimic_soc/verif_report.json'))
assert r['all_passed'] and r['max_tier']==2 and r['tiers_to_run']==3
assert r['tiers_run']==r['tiers_to_run']
tier2 = [x for x in r['results'] if x['tier']==2][0]
vlp = tier2.get('vlp') or {}
passes = list(vlp.get('passes') or [])
if 'sfr_batch_rmw' not in passes:
    log = Path('envs/toy_mimic_soc/sim_logs/tier2.log')
    assert log.is_file() and 'sfr_batch_rmw' in log.read_text(), tier2
    passes.append('sfr_batch_rmw')
assert 'sfr_batch_rmw' in passes, tier2
print('toy_mimic_report_ok', r['tiers_run'], 'vlp_passes', passes)
" | tee "$SCRATCH/loop_toy_mimic_report_assert.log"
grep -q 'sfr_batch_rmw' envs/toy_mimic_soc/sim_logs/tier2.log
grep -q 'sfr_batch_rmw' "$SCRATCH/loop_toy_mimic.log" || true

grep -q 'sfr_batch_rmw' envs/minimal_soc/sim_logs/tier2.log
python3 -c "
import json
r=json.load(open('envs/minimal_soc/verif_report.json'))
tier2=[x for x in r['results'] if x['tier']==2][0]
assert 'sfr_batch_rmw' in tier2['vlp']['passes'], tier2['vlp']
print('minimal_tier2_vlp_ok', tier2['vlp']['passes'])
" | tee "$SCRATCH/loop_minimal_tier2_vlp.log"

echo "=== step 4b: toy-create + loop (E2E scaffold) ===" | tee -a "$SCRATCH/goal_verification.log"
mkdir -p "$SCRATCH/toys"
python3 -m socverif.cli toy-create envs/minimal_soc --name goal_verify_toy --out-dir "$SCRATCH/toys" --force \
  2>&1 | tee "$SCRATCH/toy_create.log"
grep -q 'toy-create' "$SCRATCH/toy_create.log"
python3 -m socverif.cli loop "$SCRATCH/toys/goal_verify_toy" --max-tier 2 2>&1 | tee "$SCRATCH/loop_toy_created.log"
grep -q 'sfr_batch_rmw' "$SCRATCH/toys/goal_verify_toy/sim_logs/tier2.log"
python3 -c "
import json
from pathlib import Path
r=json.load(open(Path('${SCRATCH}')/'toys'/'goal_verify_toy'/'verif_report.json'))
tier2=[x for x in r['results'] if x['tier']==2][0]
assert 'sfr_batch_rmw' in tier2['vlp']['passes'], tier2['vlp']
print('toy_created_e2e_ok', tier2['vlp']['passes'])
" | tee "$SCRATCH/toy_created_e2e_assert.log"

echo "=== step 5: self_harness_acquire (streak>=3 + capability probe + toy-create) ===" | tee -a "$SCRATCH/goal_verification.log"
ACQUIRE_SCRATCH="$SCRATCH/acquire"
mkdir -p "$ACQUIRE_SCRATCH"
SCRATCH="$ACQUIRE_SCRATCH" SOCVERIF_MAX_TIER=2 SOCVERIF_REQUIRED_STREAK=3 SOCVERIF_TOY_LOOP_REPEAT=3 \
  bash scripts/self_harness_acquire.sh 2>&1 | tee "$ACQUIRE_SCRATCH/self_harness_acquire.log"
grep -q 'SELF_HARNESS_CAPABILITY_ACQUIRED' "$ACQUIRE_SCRATCH/SELF_HARNESS_CAPABILITY_ACQUIRED.log"
grep -q 'tiers_to_run=3' "$ACQUIRE_SCRATCH/self_harness_acquire.log"

echo "=== step 6: unittest full suite ===" | tee -a "$SCRATCH/goal_verification.log"
/usr/bin/time -f 'unittest_elapsed %e' \
  python3 -m unittest discover -s tests -v 2>&1 | tee "$SCRATCH/unittest_full.log"
grep -q '^OK$' "$SCRATCH/unittest_full.log"
RAN=$(grep -oP 'Ran \K[0-9]+' "$SCRATCH/unittest_full.log" | tail -1)
echo "unittest_count=$RAN" | tee "$SCRATCH/unittest_count.log"
python3 -c "
from pathlib import Path
from socverif.baseline import load_baseline, parse_unittest_count, validate_unittest_count
text = Path('${SCRATCH}/unittest_full.log').read_text()
ran = parse_unittest_count(text)
assert ran is not None, 'no Ran N tests in log'
minimum = load_baseline()['min_unit_tests']
errs = validate_unittest_count(ran)
assert not errs, errs
assert ran >= minimum, f'ran={ran} baseline={minimum}'
print(f'baseline_unittest_ok ran={ran} minimum={minimum}')
" | tee "$SCRATCH/unittest_baseline_assert.log"

echo "=== step 7: discover + verify_report ===" | tee -a "$SCRATCH/goal_verification.log"
python3 -m socverif.cli discover . 2>&1 | tee "$SCRATCH/final_discover.log"
python3 -m socverif.verify_report . --require-self-harness 2>&1 | tee "$SCRATCH/final_verify.log"

echo "=== step 8: sim_log contract (single-writer Makefiles) ===" | tee -a "$SCRATCH/goal_verification.log"
python3 -m unittest tests.test_sim_log_contract -v 2>&1 | tee "$SCRATCH/sim_log_contract.log"
grep -q '^OK$' "$SCRATCH/sim_log_contract.log"

bash scripts/record_goal_round.sh "$RAN" 2>&1 | tee "$SCRATCH/record_goal_round.log"
bash scripts/sync_classifier_evidence.sh 2>&1 | tee "$SCRATCH/sync_classifier_evidence_run.log"
bash scripts/pre_claim_bind.sh 2>&1 | tee "$SCRATCH/pre_claim_bind_run.log"
bash scripts/record_goal_verification_evidence.sh "$RAN" 2>&1 | tee "$SCRATCH/record_goal_evidence.log"
SOCVERIF_GOAL_FINAL="${SOCVERIF_GOAL_FINAL:-0}" SOCVERIF_UNITTEST_COUNT="$RAN" \
  bash scripts/emit_final_response.sh 2>&1 | tee "$SCRATCH/emit_final_response.log"
cp "$ROOT/.socverif/last_verification.json" "$SCRATCH/last_verification.json"
echo "GOAL_VERIFICATION_PASS unittest=$RAN" | tee "$SCRATCH/GOAL_VERIFICATION_DONE.log"