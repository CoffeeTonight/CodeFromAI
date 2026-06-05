#!/usr/bin/env bash
# Phase 6: SV grammar enhancements + phase7 DQL gaps
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
python -m pytest tests/phase6/ tests/phase7/test_dql_gaps.py -q -m "not slow"
echo "phase6+7 OK"