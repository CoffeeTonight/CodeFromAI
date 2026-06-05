#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
pytest tests/phase22/ -q -m "not slow"
echo "phase22 verify OK"