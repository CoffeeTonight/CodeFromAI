#!/usr/bin/env bash
# goal_build_id = 20 — default SCRATCH/GOAL_ROOT under /home/user/tools/socverif-harness-work
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
eval "$(python3 -m socverif.work_layout --shell --ensure)"
export HARNESS_SESSION_ROOT="${HARNESS_SESSION_ROOT:-$ROOT}"