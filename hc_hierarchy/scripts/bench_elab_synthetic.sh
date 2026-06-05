#!/usr/bin/env bash
# Large Tier P / Tier E benchmark on design/synthetic_deep_rtl (~991 sources).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
python3 scripts/bench_elab_synthetic.py "$@"