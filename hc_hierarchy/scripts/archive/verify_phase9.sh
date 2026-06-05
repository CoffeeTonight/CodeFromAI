#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
pip install -e ".[engine,dev]" -q
pytest tests/phase9/ -q "$@"