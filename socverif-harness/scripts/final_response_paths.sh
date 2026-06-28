#!/usr/bin/env bash
# goal_build_id = 12 — FINAL_RESPONSE may cite ONLY round_paths.jsonl entries
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SINCE="${SOCVERIF_ROUND_SINCE:-$ROOT/.socverif/round_start_ts}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
cd "$ROOT"

if [[ ! -f "$SINCE" ]]; then
  echo "final_response_paths: missing $SINCE" >&2
  exit 2
fi

python3 -m socverif.round_paths list-only --since-file "$SINCE"