#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pytest tests/phase0 tests/phase1 -v --tb=short
echo "Phase 1 PASS"