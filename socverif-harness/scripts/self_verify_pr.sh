#!/usr/bin/env bash
# goal_build_id = 12 — fast PR gate (tier 0-1)
set -euo pipefail
export SOCVERIF_MAX_TIER=1
exec "$(dirname "$0")/verify_goal.sh"