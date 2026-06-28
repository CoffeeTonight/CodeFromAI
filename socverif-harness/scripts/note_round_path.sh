#!/usr/bin/env bash
# goal_build_id = 12 — append path to round_paths.jsonl (PRIMARY); hunk secondary audit
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
if [[ $# -lt 1 ]]; then
  echo "usage: $0 <harness-relative-path>" >&2
  exit 2
fi
cd "$ROOT"
python3 -m socverif.round_paths note "$1"
python3 -m socverif.hunk_tracking note "$1" 2>/dev/null || true