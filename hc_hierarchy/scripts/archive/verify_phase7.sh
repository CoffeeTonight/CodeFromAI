#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pytest tests/phase0 tests/phase1 tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/phase7 -v --tb=short -m "not slow"
echo "Phase 7 PASS (fast)"