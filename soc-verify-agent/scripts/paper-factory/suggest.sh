#!/usr/bin/env bash
set -euo pipefail
ROOT="${SOC_VERIFY_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
CAMPAIGN="${1:-paper_eval_2026}"
shift || true
if command -v paper-factory >/dev/null 2>&1; then
  exec paper-factory --root "$ROOT" suggest --campaign "$CAMPAIGN" "$@"
fi
PY="${PYTHON:-python3}"
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$PY" -m soc_verify.paper_factory_cli --root "$ROOT" suggest --campaign "$CAMPAIGN" "$@"