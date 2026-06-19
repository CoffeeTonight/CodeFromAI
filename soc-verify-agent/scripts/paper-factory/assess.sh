#!/usr/bin/env bash
set -euo pipefail
ROOT="${SOC_VERIFY_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
CAMPAIGN="${1:-paper_eval_2026}"
shift || true
_run() {
  if command -v paper-factory >/dev/null 2>&1; then
    paper-factory --root "$ROOT" assess --campaign "$CAMPAIGN" --write "$@"
    return
  fi
  PY="${PYTHON:-python3}"
  PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
    "$PY" -m soc_verify.paper_factory_cli --root "$ROOT" assess --campaign "$CAMPAIGN" --write "$@"
}
_run "$@"