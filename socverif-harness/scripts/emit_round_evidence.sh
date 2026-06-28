#!/usr/bin/env bash
# goal_build_id = 12 — ROUND_EVIDENCE from workspace_delta (git-first)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${1:?usage: emit_round_evidence.sh <scratch-dir>}"
SINCE="${SOCVERIF_ROUND_SINCE:-$ROOT/.socverif/round_start_ts}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
cd "$ROOT"

python3 -m socverif.round_evidence emit --scratch "$SCRATCH" --since-file "$SINCE"
python3 -c "
import json
from pathlib import Path
ev = json.loads((Path('${SCRATCH}') / 'ROUND_EVIDENCE.json').read_text())
assert ev.get('ok'), ev
if ev.get('gate_only'):
    print('ROUND_EVIDENCE gate-only count=0')
else:
    print(f\"ROUND_EVIDENCE ok count={ev['count']} source={ev.get('source')}\")
" | tee "$SCRATCH/round_evidence_ok.log"
grep -qE 'ROUND_EVIDENCE (ok|gate-only)' "$SCRATCH/round_evidence_ok.log"