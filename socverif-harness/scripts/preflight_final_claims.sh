#!/usr/bin/env bash
# goal_build_id = 12 — round_paths must match delivery_bundle before FINAL claims
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch}"
SINCE="${SOCVERIF_ROUND_SINCE:-$ROOT/.socverif/round_start_ts}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH"
cd "$ROOT"

if [[ ! -f "$SINCE" ]]; then
  echo "preflight_final_claims: missing $SINCE" >&2
  exit 2
fi

python3 -m socverif.round_paths preflight --since-file "$SINCE" \
  2>&1 | tee "$SCRATCH/preflight_final_claims.json"

python3 -c "
import json
from pathlib import Path
r = json.loads(Path('${SCRATCH}/preflight_final_claims.json').read_text())
assert r.get('ok'), r
if r.get('gate_only'):
    print('PREFLIGHT_FINAL_CLAIMS gate-only count=0 — zero source edits claimed')
else:
    print(f\"PREFLIGHT_FINAL_CLAIMS ok count={r['count']} source={r.get('source')}\")
" | tee "$SCRATCH/preflight_final_claims.log"

grep -qE 'PREFLIGHT_FINAL_CLAIMS (ok|gate-only)' "$SCRATCH/preflight_final_claims.log"