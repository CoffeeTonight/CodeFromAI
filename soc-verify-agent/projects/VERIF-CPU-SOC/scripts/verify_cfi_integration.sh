#!/usr/bin/env bash
# Verify ~/tools/__CFI integration — exit 0 only when all checks pass.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOC_ROOT="$(cd "$ROOT/../.." && pwd)"
CFI="${HOME}/tools/__CFI"
RTL="${CFI}/VerifCPU/verif_cpu_verilog"
SCAN="${CFI}/hierwalk"
FAIL=0

fail() { echo "[FAIL] $*"; FAIL=1; }
pass() { echo "[PASS] $*"; }

echo "=== CFI integration verify ==="

# 1. Local paths exist
[[ -f "${RTL}/example.sh" ]] && pass "RTL example.sh" || fail "missing ${RTL}/example.sh"
[[ -f "${RTL}/howto_integrate.md" ]] && pass "howto_integrate.md" || fail "missing howto_integrate.md"
[[ -f "${RTL}/vcpu_skill.md" ]] && pass "vcpu_skill.md" || fail "missing vcpu_skill.md"
[[ -d "${SCAN}/src" ]] && pass "hierwalk src" || fail "missing ${SCAN}/src"

# 2. discovered + cache
python3 - <<'PY' "$ROOT" "$CFI" || exit 1
import sys, yaml
from pathlib import Path
root, cfi = Path(sys.argv[1]), Path(sys.argv[2])
d = yaml.safe_load((root / "discovered.yaml").read_text()) or {}
c = yaml.safe_load((root / "cache.yaml").read_text()) or {}
assert d.get("local_clone_path"), "discovered.yaml missing local_clone_path"
assert d.get("rtl_subdir") == "VerifCPU/verif_cpu_verilog", "rtl_subdir mismatch"
clone = (c.get("clone") or {}).get("path")
assert clone and Path(str(clone)).resolve() == cfi.resolve(), f"cache clone.path != {cfi}"
print("[PASS] discovered.yaml + cache.yaml")
PY

# 3. bootstrap idempotent
cd "$ROOT"
./scripts/bootstrap_verifcpu_workspace.sh >/tmp/bootstrap_verify.log 2>&1 \
  && pass "bootstrap_verifcpu_workspace.sh" \
  || { cat /tmp/bootstrap_verify.log; fail "bootstrap failed"; }

# 4. resolve_rtl_root
RESOLVED="$(python3 -c "import sys; sys.path.insert(0,'$ROOT'); from ops.intake_resolve import resolve_rtl_root; from pathlib import Path; print(resolve_rtl_root(Path('$ROOT')))")"
if [[ "$RESOLVED" == "$(cd "$RTL" && pwd)" ]]; then
  pass "resolve_rtl_root=$RESOLVED"
else
  fail "resolve_rtl_root=$RESOLVED expected $RTL"
fi

# 5. Key docs reference __CFI (not workspace clone as primary)
DOCS=(
  "$ROOT/USER-PROCEDURE.md"
  "$ROOT/howto_integrate2yourSoC.md"
  "$ROOT/scripts/README.md"
  "$SOC_ROOT/README.md"
  "$SOC_ROOT/templates/obsidian/agent/vcpu-soc-integration/00-INTEGRATION-HUB.md"
)
for doc in "${DOCS[@]}"; do
  if rg -q '__CFI|~/tools/__CFI' "$doc" 2>/dev/null; then
    pass "doc cites __CFI: $(basename "$doc")"
  else
    fail "doc missing __CFI ref: $doc"
  fi
done
# Primary SSOT must not tell users to start from workspace/main
if rg -n 'workspace/main' "${DOCS[@]}" 2>/dev/null; then
  fail "doc still cites workspace/main as primary"
else
  pass "no workspace/main as primary in key docs"
fi

# 6. expand runbook
python3 "$ROOT/scripts/expand_agent_runbook.py" \
  --intake "$ROOT/inputs/tags/main/deployment/customer_soc_intake.example.yaml" \
  >/tmp/runbook_expand.log 2>&1 \
  && pass "expand_agent_runbook.py" \
  || { cat /tmp/runbook_expand.log; fail "expand_agent_runbook failed"; }

# 7. crystallize gates
python3 "$ROOT/scripts/crystallize_gate_from_intake.py" \
  --intake "$ROOT/inputs/tags/main/deployment/customer_soc_intake.example.yaml" \
  >/tmp/crystallize.log 2>&1 \
  && pass "crystallize_gate_from_intake.py" \
  || { cat /tmp/crystallize.log; fail "crystallize failed"; }

# 8. pytest
cd "$SOC_ROOT"
pytest tests/test_intake_resolve.py tests/test_coi_conn_pipeline.py tests/test_verifcpu_log.py -q \
  >/tmp/pytest_cfi.log 2>&1 \
  && pass "pytest VERIF-CPU-SOC tests" \
  || { tail -20 /tmp/pytest_cfi.log; fail "pytest failed"; }

# Drop crystallized overrides (regenerate via crystallize_gate_from_intake.py before gates)
rm -f "$ROOT/inputs/tags/main/overrides/coi_conn_checks.json" \
      "$ROOT/inputs/tags/main/overrides/slave_rw_scenarios.json"

if [[ $FAIL -ne 0 ]]; then
  echo "=== VERIFY: FAIL ==="
  exit 1
fi
echo "=== VERIFY: PASS ==="
exit 0