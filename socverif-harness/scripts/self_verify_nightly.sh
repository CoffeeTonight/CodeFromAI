#!/usr/bin/env bash
# goal_build_id = 12 — full nightly gate (tier 0-2 + reference envs)
set -euo pipefail
export SOCVERIF_MAX_TIER=2
exec "$(dirname "$0")/verify_goal.sh"