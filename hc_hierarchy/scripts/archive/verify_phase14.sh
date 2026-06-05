#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
pip install -e ".[engine,dev]" -q
pytest tests/phase14/ tests/phase10/ tests/phase11/ tests/phase12/ tests/phase13/ tests/phase9/ -q "$@"