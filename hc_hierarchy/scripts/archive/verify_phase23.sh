#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
pytest tests/phase23/ -q -m "not slow"
echo "phase23 verify OK"