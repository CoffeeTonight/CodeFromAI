#!/usr/bin/env bash
# Work-folder wrapper for __CFA soc-verify-agent self-harness CLI
set -euo pipefail

SOC_VERIFY_ROOT="${SOC_VERIFY_ROOT:-$HOME/tools/__CFA/soc-verify-agent}"
WORK_ROOT="${SOC_VERIFY_WORK_ROOT:-$HOME/tools/soc-verify-agent-work}"
SCRIPT="${SOC_VERIFY_ROOT}/projects/VERIF-CPU-SOC/scripts/self_harness.sh"

if [[ ! -x "$SCRIPT" ]]; then
  chmod +x "$SCRIPT" 2>/dev/null || true
fi
[[ -f "$SCRIPT" ]] || { echo "missing self_harness.sh: $SCRIPT" >&2; exit 1; }

export SOC_VERIFY_WORK_ROOT="$WORK_ROOT"
export PROJECT_DIR="${SOC_VERIFY_ROOT}/projects/VERIF-CPU-SOC"
exec bash "$SCRIPT" "$@"