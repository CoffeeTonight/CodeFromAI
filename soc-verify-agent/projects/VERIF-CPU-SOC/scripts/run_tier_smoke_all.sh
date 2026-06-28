#!/usr/bin/env bash
# Run all three integration tier smokes (iverilog) — vault 13-INTEGRATION-TIERS SSOT.
# Tier 3 scale smoke = make chip-top-example (13-INTEGRATION-TIERS SSOT).
# Post-make gen manifest VH checks run after tier 2 and tier 3 (read-only intake_resolve).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RTL="${1:-${RTL_ROOT:-}}"
SCRATCH="${2:-}"
if [[ -z "$RTL" || ! -f "$RTL/Makefile" ]]; then
  echo "usage: $0 /path/to/verif_cpu_verilog [scratch_dir]" >&2
  exit 1
fi

validate_manifest_headers() {
  echo "=== manifest header validation (post-gen, intake_resolve) ==="
  python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from pathlib import Path
from ops.intake_resolve import assert_manifest_generated_headers
assert_manifest_generated_headers(Path('$RTL'))
print('[PASS] manifest generated headers valid')
"
}

log_dir() {
  if [[ -n "$SCRATCH" ]]; then
    mkdir -p "$SCRATCH"
    echo "$SCRATCH"
  else
    echo "/tmp"
  fi
}

cd "$RTL"
LOGDIR="$(log_dir)"

echo "=== tier 1 paste: make soc-paste ==="
make soc-paste 2>&1 | tee "$LOGDIR/smoke_tier1_paste.log"
grep -E 'soc_cpu_bus_paste: PASS|4 passed' "$LOGDIR/smoke_tier1_paste.log"

echo "=== tier 2 yaml_multi: make gen && make soc-integration ==="
bash -c 'make gen && make soc-integration' 2>&1 | tee "$LOGDIR/smoke_tier2_yaml.log"
grep -E 'soc_integration_example: PASS|12 passed' "$LOGDIR/smoke_tier2_yaml.log"
validate_manifest_headers 2>&1 | tee -a "$LOGDIR/smoke_tier2_yaml.log"

echo "=== tier 3 scale: make chip-top-example (13-INTEGRATION-TIERS SSOT) ==="
make chip-top-example 2>&1 | tee "$LOGDIR/smoke_tier3_scale.log"
grep -E 'chip_top_example|16 passed' "$LOGDIR/smoke_tier3_scale.log"
validate_manifest_headers 2>&1 | tee -a "$LOGDIR/smoke_tier3_scale.log"

echo "[PASS] all tier smokes (paste, yaml_multi, scale)"