#!/usr/bin/env bash
# goal_build_id = 20 — seal mirror patch + prune session hunks + verify-disk
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

echo "=== freeze_classifier_snapshot: seal_classifier_evidence ===" | tee "$SCRATCH/freeze_classifier.log"
python3 -m socverif.classifier_capture seal \
  --scratch "$SCRATCH" \
  --goal-root "$GOAL_ROOT" \
  --harness-root "$ROOT" \
  2>&1 | tee -a "$SCRATCH/freeze_classifier.log"

test -f "$SCRATCH/CLASSIFIER_WITNESS.patch"
test -f "$SCRATCH/CLASSIFIER_MIRROR.patch"
test -f "$GOAL_ROOT/CLASSIFIER_WITNESS.patch"
test -f "$GOAL_ROOT/CLASSIFIER_MIRROR.patch"

python3 -m socverif.classifier_capture verify-disk \
  --scratch "$SCRATCH" \
  --goal-root "$GOAL_ROOT" \
  --harness-root "$ROOT" \
  2>&1 | tee "$SCRATCH/freeze_verify_disk.log"

grep -q '"ok": true' "$SCRATCH/freeze_verify_disk.log"

python3 -c "
import json, re
from pathlib import Path
from socverif.classifier_anchor import paths_in_patch, resolve_classifier_attempt_patch
goal = Path('$GOAL_ROOT')
scratch = Path('$SCRATCH')
witness = scratch / 'CLASSIFIER_WITNESS.patch'
mirror = scratch / 'CLASSIFIER_MIRROR.patch'
attempt = resolve_classifier_attempt_patch(goal)
w = witness.read_text(encoding='utf-8')
m = mirror.read_text(encoding='utf-8')
a = attempt.read_text(encoding='utf-8')
paths = set(paths_in_patch(a))
proof = {
    'witness_bytes': len(w.encode()),
    'mirror_bytes': len(m.encode()),
    'attempt_bytes': len(a.encode()),
    'mirror_match_attempt': m == a,
    'witness_paths': len(paths_in_patch(w)),
    'mirror_paths': len(paths_in_patch(m)),
    'attempt_paths': len(paths),
    'has_grok_path': any('.grok/' in p for p in paths),
    'attempt': str(attempt),
}
(scratch / 'freeze_on_disk_proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof, indent=2))
if not proof['mirror_match_attempt']:
    raise SystemExit('CLASSIFIER_MIRROR != attempt on disk')
if proof['has_grok_path']:
    raise SystemExit('attempt patch has .grok paths')
" 2>&1 | tee "$SCRATCH/freeze_on_disk_proof.log"

echo "FREEZE_CLASSIFIER_SNAPSHOT_PASS" | tee "$SCRATCH/FREEZE_CLASSIFIER_DONE.log"