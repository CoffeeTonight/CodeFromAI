#!/usr/bin/env bash
# Hermes-style first-time setup — interactive TUI
set -euo pipefail
ROOT="${SOC_VERIFY_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
if command -v soc-verify >/dev/null 2>&1; then
  exec soc-verify --root "$ROOT" setup "$@"
fi
PY="${PYTHON:-python3}"
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$PY" -m soc_verify.cli --root "$ROOT" setup "$@"