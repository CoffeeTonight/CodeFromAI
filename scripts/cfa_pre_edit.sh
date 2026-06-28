#!/usr/bin/env bash
# Wrapper: snapshot then run command. Agents should use this for CFA edits.
#   bash scripts/cfa_pre_edit.sh make soc-paste
#   bash scripts/cfa_pre_edit.sh --label gate-run -- bash projects/.../run_plan_gates.sh /tmp/scratch
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="pre-edit"
if [[ "${1:-}" == "--label" ]]; then
  LABEL="${2:?}"
  shift 2
fi
[[ $# -ge 1 ]] || { echo "usage: cfa_pre_edit.sh [--label NAME] COMMAND ..." >&2; exit 2; }

export CFA_ROOT="$ROOT"
bash "$ROOT/scripts/cfa_snapshot_backup.sh" "$LABEL"
exec "$@"