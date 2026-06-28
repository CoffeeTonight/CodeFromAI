#!/usr/bin/env bash
# goal_build_id = 12 — emit round_paths logged this round (sole FINAL source)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SINCE="${SOCVERIF_ROUND_SINCE:-$ROOT/.socverif/round_start_ts}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
cd "$ROOT"

if [[ ! -f "$SINCE" ]]; then
  echo "emit_round_changed_paths: missing $SINCE" >&2
  exit 2
fi

python3 -m socverif.round_paths list-only --since-file "$SINCE"