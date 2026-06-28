#!/usr/bin/env bash
# goal_build_id = 12
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HARNESS_ROOT="$(cd "$ROOT/../.." && pwd)"
export PYTHONPATH="${HARNESS_ROOT}:${PYTHONPATH:-}"
cd "$ROOT"
mkdir -p logs build
test -f build/chip.vvp || bash scripts/compile.sh
python3 -m socverif.sim_log run 'vvp build/chip.vvp' 'logs/tier0.log'