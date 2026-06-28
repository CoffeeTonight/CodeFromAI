#!/usr/bin/env bash
# goal_build_id = 12 — persist verification summary + round paths into harness tree
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch/round}"
SINCE="${SOCVERIF_ROUND_SINCE:-$ROOT/.socverif/round_start_ts}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH" "$ROOT/.socverif"
cd "$ROOT"

ROUND_TS="$(cat "$SINCE" 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)"
bash scripts/emit_round_changed_paths.sh > "$SCRATCH/round_changed_paths.txt"
bash scripts/emit_round_evidence.sh "$SCRATCH" 2>&1 | tee -a "$SCRATCH/record_goal_round.log"
python3 -m socverif.delivery_bundle emit --scratch "$SCRATCH" 2>&1 | tee -a "$SCRATCH/record_goal_round.log"
bash scripts/final_response_paths.sh > "$SCRATCH/final_response_paths.txt"
UNITTEST="${1:-unknown}"

python3 -c "
import json
from datetime import datetime, timezone
from pathlib import Path
root = Path('${ROOT}')
scratch = Path('${SCRATCH}')
paths = [p.strip() for p in (scratch / 'round_changed_paths.txt').read_text().splitlines() if p.strip()]
out = {
    'goal_build_id': 12,
    'recorded_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'round_start_ts': '${ROUND_TS}'.strip(),
    'unittest_count': '${UNITTEST}',
    'round_changed_paths': paths,
    'scratch': str(scratch),
}
path = root / '.socverif' / 'last_verification.json'
path.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print('wrote', path)
print('round_paths', len(paths))
"

python3 -m socverif.hunk_tracking append --from-file "$SCRATCH/round_changed_paths.txt" \
  2>&1 | tee -a "$SCRATCH/record_goal_round.log"