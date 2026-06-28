#!/usr/bin/env bash
# goal_build_id = 20 — create /home/user/tools/socverif-harness-work layout
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
python3 -m socverif.work_layout --json --ensure
source "$ROOT/scripts/resolve_goal_env.sh"
echo "work_layout_ready scratch=$SCRATCH goal_root=$SOCVERIF_GOAL_ROOT outer=$GROK_WORKSPACE_ROOT"