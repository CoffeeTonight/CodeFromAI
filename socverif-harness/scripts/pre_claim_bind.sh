#!/usr/bin/env bash
# goal_build_id = 20 — mandatory before update_goal(completed:true)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
if [[ -z "${SCRATCH:-}" || -z "${SOCVERIF_GOAL_ROOT:-}" ]]; then
  # shellcheck source=scripts/resolve_goal_env.sh
  source "$ROOT/scripts/resolve_goal_env.sh"
fi
SCRATCH="${SCRATCH:?SCRATCH unset}"
GOAL_ROOT="${SOCVERIF_GOAL_ROOT:?SOCVERIF_GOAL_ROOT unset}"
mkdir -p "$SCRATCH"
cd "$ROOT"

export SOCVERIF_CFA_HARNESS="$ROOT"
export HARNESS_SESSION_ROOT="${HARNESS_SESSION_ROOT:-$ROOT}"
export SOCVERIF_GOAL_ROOT="$GOAL_ROOT"

echo "=== pre_claim_bind: prepare_classifier_capture (round_paths only) ===" | tee "$SCRATCH/pre_claim_bind.log"
python3 -c "
import json
from socverif.classifier_evidence import prepare_classifier_capture
print(json.dumps(prepare_classifier_capture(), indent=2))
" 2>&1 | tee -a "$SCRATCH/pre_claim_bind.log"

echo "=== pre_claim_bind: round_paths audit (note_round_path evidence) ===" | tee -a "$SCRATCH/pre_claim_bind.log"
python3 -m socverif.round_paths list-only --since-file "$ROOT/.socverif/round_start_ts" \
  | while IFS= read -r rel; do
      echo "bash scripts/note_round_path.sh $rel"
    done | tee "$SCRATCH/note_round_path_audit.log" | tee -a "$SCRATCH/pre_claim_bind.log"

echo "=== pre_claim_bind: freeze_classifier_snapshot (attempt patch only) ===" | tee -a "$SCRATCH/pre_claim_bind.log"
bash scripts/freeze_classifier_snapshot.sh 2>&1 | tee -a "$SCRATCH/pre_claim_bind.log"

export CHANGES_FILE="$(python3 -c "
from pathlib import Path
from socverif.classifier_anchor import resolve_classifier_attempt_patch
print(resolve_classifier_attempt_patch(Path('$GOAL_ROOT')), end='')
")"
echo "CHANGES_FILE=$CHANGES_FILE" | tee "$SCRATCH/CHANGES_FILE_env.log" | tee -a "$SCRATCH/pre_claim_bind.log"
echo "source $SCRATCH/classifier_env.sh before update_goal(completed:true)" | tee -a "$SCRATCH/pre_claim_bind.log"

echo "=== pre_claim_bind: assert_anchors (attempt patch only) ===" | tee -a "$SCRATCH/pre_claim_bind.log"
python3 -m socverif.classifier_anchor assert \
  --scratch "$SCRATCH" \
  --goal-root "$GOAL_ROOT" \
  --harness-root "$ROOT" \
  2>&1 | tee "$SCRATCH/pre_claim_assert.log"

grep -q '"ok": true' "$SCRATCH/pre_claim_assert.log"

python3 -c "
import json
from pathlib import Path
from socverif.classifier_anchor import (
    paths_in_patch,
    resolve_classifier_attempt_patch,
    resolve_classifier_attempt_number,
)
from socverif.classifier_capture import mirror_changed_paths, mirror_path_file
goal = Path('$GOAL_ROOT')
scratch = Path('$SCRATCH')
changed = [ln.strip() for ln in (scratch / 'CHANGED_FILES').read_text().splitlines() if ln.strip()]
attempt = resolve_classifier_attempt_patch(goal)
allowed = set(mirror_changed_paths(changed))
proof = []
if attempt.is_file():
    body = attempt.read_text(encoding='utf-8')
    paths = set(paths_in_patch(body))
    mirror_ok = mirror_path_file(scratch).is_file() and body == mirror_path_file(scratch).read_text(encoding='utf-8')
    proof.append(
        f'attempt_{resolve_classifier_attempt_number(goal)}: {attempt.name} '
        f'bytes={len(body.encode())} paths={len(paths)} ok={paths == allowed and mirror_ok}'
    )
with (scratch / 'harness-prompt-proof.txt').open('w', encoding='utf-8') as fh:
    fh.write('\n'.join(proof) + '\n')
    fh.write(f'CHANGES_FILE: {attempt} bytes={attempt.stat().st_size if attempt.is_file() else 0}\n')
print(json.dumps({'proof_lines': proof, 'changes_file': str(attempt)}, indent=2))
" | tee "$SCRATCH/harness_prompt_proof.log"

echo "=== pre_claim_bind: verify-disk (witness == attempt bytes) ===" | tee -a "$SCRATCH/pre_claim_bind.log"
python3 -m socverif.classifier_capture verify-disk \
  --scratch "$SCRATCH" \
  --goal-root "$GOAL_ROOT" \
  --harness-root "$ROOT" \
  2>&1 | tee "$SCRATCH/pre_claim_verify_disk.log"
grep -q '"ok": true' "$SCRATCH/pre_claim_verify_disk.log"

echo "PRE_CLAIM_BIND_PASS" | tee "$SCRATCH/PRE_CLAIM_BIND_DONE.log"