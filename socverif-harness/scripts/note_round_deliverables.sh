#!/usr/bin/env bash
# goal_build_id = 12 — note all core deliverables touched this round (round_delta honesty)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
cd "$ROOT"

PATHS=(
  socverif/round_paths.py
  socverif/delivery_bundle.py
  socverif/round_evidence.py
  scripts/begin_goal_round.sh
  scripts/note_round_path.sh
  scripts/emit_round_changed_paths.sh
  scripts/final_response_paths.sh
  scripts/emit_final_response.sh
  scripts/preflight_final_claims.sh
  scripts/run_goal_verification.sh
  scripts/record_goal_verification_evidence.sh
  scripts/sync_baseline_literals.sh
  tests/test_round_paths_unified.py
  tests/test_delivery_honesty.py
  tests/test_round_evidence.py
  docs/eda_tool.md
  docs/failed_flow.md
)

for p in "${PATHS[@]}"; do
  if [[ -f "$ROOT/$p" ]]; then
    bash "$ROOT/scripts/note_round_path.sh" "$p"
  fi
done

echo "noted_deliverables=${#PATHS[@]}"