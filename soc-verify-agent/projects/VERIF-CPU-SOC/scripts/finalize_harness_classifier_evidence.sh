#!/usr/bin/env bash
# Terminal CFA evidence seal (canonical path only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFA="$(cd "$ROOT/../../.." && pwd)"
SCRATCH="${1:-${GOAL_SCRATCH:-/tmp/grok-goal/implementer}}"
GOAL_ROOT="$(dirname "$SCRATCH")"
CHANGED_FLAT="$SCRATCH/CHANGED_FILES"
export HARNESS_SESSION_ROOT="${HARNESS_SESSION_ROOT:-${CLAUDE_PROJECT_DIR:-$GOAL_ROOT/session}}"
python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import seal_classifier_evidence
from ops.intake_resolve import _goal_non_blank_lines
changed_flat = Path('$CHANGED_FLAT')
dirty = _goal_non_blank_lines(changed_flat.read_text(encoding='utf-8')) if changed_flat.is_file() else []
sealed = seal_classifier_evidence(
    Path('$GOAL_ROOT'), Path('$SCRATCH'), Path('$CFA'), dirty,
    scratch_changed_files=changed_flat,
)
print('sealed:', sealed)
"