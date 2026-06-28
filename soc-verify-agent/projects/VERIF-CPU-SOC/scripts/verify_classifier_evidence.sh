#!/usr/bin/env bash
# Live classifier evidence: seal canonical patch, purge round-numbered files, assert CFA.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFA="$(cd "$ROOT/../../.." && pwd)"
SCRATCH="${1:-${GOAL_SCRATCH:-/tmp/grok-goal/implementer}}"
GOAL_ROOT="$(dirname "$SCRATCH")"
CHANGED_FLAT="$SCRATCH/CHANGED_FILES"
export HARNESS_SESSION_ROOT="${HARNESS_SESSION_ROOT:-${CLAUDE_PROJECT_DIR:-$GOAL_ROOT/session}}"
export GOAL_SCRATCH="$SCRATCH"

python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import (
    assert_all_classifier_patches_cfa,
    classifier_proof_is_stale,
    resolve_latest_classifier_patch,
    seal_classifier_evidence,
)
from ops.intake_resolve import _goal_non_blank_lines
goal_root = Path('$GOAL_ROOT')
scratch = Path('$SCRATCH')
changed_flat = Path('$CHANGED_FLAT')
dirty = _goal_non_blank_lines(changed_flat.read_text(encoding='utf-8')) if changed_flat.is_file() else []
proof_path = scratch / 'harness-prompt-proof.txt'
was_stale = classifier_proof_is_stale(goal_root, proof_path)
sealed = seal_classifier_evidence(
    goal_root, scratch, Path('$CFA'), dirty,
    scratch_changed_files=changed_flat,
)
assert_all_classifier_patches_cfa(goal_root)
canonical = resolve_latest_classifier_patch(goal_root)
if canonical.resolve() != sealed.resolve():
    raise SystemExit(f'seal/canonical mismatch: sealed={sealed} canonical={canonical}')
if classifier_proof_is_stale(goal_root, proof_path):
    raise SystemExit(f'proof still stale vs {canonical}')
if was_stale:
    print('refreshed stale harness-prompt-proof for canonical patch')
patch_count = len(list(goal_root.glob('goal-classifier-*.patch')))
print(f'canonical patch count: {patch_count}')
print('sealed:', sealed)
print('assert_all_classifier_patches_cfa: OK')
proof = proof_path.read_text(encoding='utf-8')
print(proof, end='')
print('verify_classifier_evidence: OK')
"

export CHANGES_FILE="$(python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import resolve_latest_classifier_patch
p = resolve_latest_classifier_patch(Path('$GOAL_ROOT'))
print(p or '', end='')
")"