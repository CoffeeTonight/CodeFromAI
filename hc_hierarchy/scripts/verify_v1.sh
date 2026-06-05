#!/usr/bin/env bash
# Tier contract v1 gate (fast). Full synthetic: HCH_SKIP_SYNTH_INDEX=0 $0
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

echo "== tier contract v1 =="
bash scripts/verify_phase27.sh

echo "== phase26 pruned elab =="
pytest tests/phase26/test_pruned_closure_elab.py tests/phase26/test_slang_diag.py -q

echo "OK verify_v1"