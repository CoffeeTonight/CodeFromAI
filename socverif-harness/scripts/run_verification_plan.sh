#!/usr/bin/env bash
# goal_build_id = 12 — PR default tier 1; nightly SOCVERIF_MAX_TIER=2
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch/plan}"
MAX_TIER="${SOCVERIF_MAX_TIER:-1}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$SCRATCH" "$ROOT/.socverif/scratch/selftest"
cd "$ROOT"

echo "=== step 1: pip install + discover ===" | tee "$SCRATCH/plan_step1.log"
python3 -m pip install -e . --quiet 2>&1 | tee -a "$SCRATCH/pip_install.log"
python3 -m socverif.cli discover . 2>&1 | tee "$SCRATCH/discover_self.log"
grep -q wrote "$SCRATCH/discover_self.log"
grep -q "self_harness=true" "$SCRATCH/discover_self.log"

echo "=== step 2: inspect ===" | tee "$SCRATCH/plan_step2.log"
python3 -m socverif.cli inspect . --json 2>&1 | tee "$SCRATCH/inspect_self.log"
grep -q self_harness "$SCRATCH/inspect_self.log"

echo "=== step 3: self-harness loop (max-tier=$MAX_TIER) ===" | tee "$SCRATCH/plan_step3.log"
python3 -m socverif.cli loop . --max-tier "$MAX_TIER" 2>&1 | tee "$SCRATCH/self_harness_loop.log"
python3 -m socverif.verify_report . --require-self-harness 2>&1 | tee "$SCRATCH/verify_report.log"

echo "=== step 4: help ===" | tee "$SCRATCH/plan_step4.log"
python3 -m socverif.cli --help 2>&1 | tee "$SCRATCH/help_evidence.log"
for sub in discover run loop instrument inspect; do grep -q "$sub" "$SCRATCH/help_evidence.log"; done

echo "VERIFICATION_PLAN_PASS" | tee "$SCRATCH/VERIFICATION_PLAN_DONE.log"