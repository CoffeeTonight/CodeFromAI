#!/usr/bin/env bash
# goal_build_id = 12 — round_start_ts + round_paths marker (+ optional snapshot audit)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
cd "$ROOT"
mkdir -p "$ROOT/.socverif"

date -u +%Y-%m-%dT%H:%M:%SZ > "$ROOT/.socverif/round_start_ts"
python3 -m socverif.round_paths mark-round --since-file "$ROOT/.socverif/round_start_ts"
python3 -m socverif.workspace_delta capture --since-file "$ROOT/.socverif/round_start_ts" >/dev/null
echo "begin_goal_round: ts=$(cat "$ROOT/.socverif/round_start_ts") round_paths=PRIMARY"