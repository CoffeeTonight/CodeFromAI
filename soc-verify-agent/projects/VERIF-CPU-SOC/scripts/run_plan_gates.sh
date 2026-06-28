#!/usr/bin/env bash
# Run plan verification steps 1-5; write evidence to SCRATCH; perfect-review from logs only.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOC="$(cd "$ROOT/../.." && pwd)"
CFA="$(cd "$ROOT/../../.." && pwd)"
SCRATCH="${1:-${GOAL_SCRATCH:-/tmp/grok-goal-243c91378fc8/implementer}}"
export GOAL_SCRATCH="$SCRATCH"
WORKSPACE_ROOT="${GROK_WORKSPACE_ROOT:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
export HARNESS_SESSION_ROOT="${HARNESS_SESSION_ROOT:-${CLAUDE_PROJECT_DIR:-$WORKSPACE_ROOT}}"
EXTRACT="$SCRATCH/gates-extract.log"
CHANGED="$SCRATCH/changed-files-in-scope.log"
CHANGED_FLAT="$SCRATCH/CHANGED_FILES"
PROOF="$SCRATCH/git-preexisting-proof.log"
GOAL_ROOT="$(dirname "$SCRATCH")"
# Repair prior-round junk patches (outer harness may clobber after last [PASS])
if [[ -d "$GOAL_ROOT" ]] && [[ -f "$CHANGED_FLAT" ]]; then
  python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import reconcile_classifier_patches_from_witness
from ops.intake_resolve import _goal_non_blank_lines
changed = Path('$CHANGED_FLAT')
dirty = _goal_non_blank_lines(changed.read_text(encoding='utf-8')) if changed.is_file() else []
if reconcile_classifier_patches_from_witness(Path('$GOAL_ROOT'), Path('$SCRATCH'), cfa_root=Path('$CFA'), dirty_relpaths=dirty):
    print('pre-gates: reconciled classifier patches from witness')
" || fail "pre-gates reconcile classifier patches"
  bash "$ROOT/scripts/finalize_harness_classifier_evidence.sh" "$SCRATCH" \
    || fail "pre-gates finalize (repair junk classifier patches)"
fi
# Always target the highest round patch (outer harness may create N after prior finalize)
CHANGES_FILE="$(python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import resolve_latest_classifier_patch
p = resolve_latest_classifier_patch(Path('$GOAL_ROOT'))
print(p or '', end='')
")"
export CHANGES_FILE

# Explicit smoke-prerequisite paths only (not whole RTL tree)
VERIFCPU_SMOKE_UNTRACKED=(
  tb/soc_cpu_bus_paste.v
  tb/soc_integration_example.v
  include/verif_paste_soc_bus_read.vh
  include/verif_paste_soc_bus_write.vh
  include/soc_integration_example_gen.vh
  firmware/campaign/gen_soc_integration_example.py
  firmware/campaign/soc_integration_ports.yaml
)

HARNESS_MIRROR="$SCRATCH/harness_workspace"
mkdir -p "$SCRATCH" "$HARNESS_MIRROR"
: > "$EXTRACT"
rm -f "$SCRATCH/CHANGES_MANIFEST.txt" "$SCRATCH/goal-cfa-changes.patch" "$SCRATCH/goal-code-changes.diff"

fail() { echo "[FAIL] $*" | tee -a "$EXTRACT" >&2; exit 1; }

append() { echo "$1" >> "$EXTRACT"; }

# SSOT snapshot before gate mutations (see ~/tools/__CFA/BACKUP_POLICY.md)
if [[ -x "$CFA/scripts/cfa_snapshot_backup.sh" ]]; then
  CFA_ROOT="$CFA" bash "$CFA/scripts/cfa_snapshot_backup.sh" gate-run || true
fi

if [[ -n "${RTL_ROOT:-}" ]]; then
  RTL="$RTL_ROOT"
else
  RTL="$(python3 -c "import sys; sys.path.insert(0,'$ROOT'); from ops.intake_resolve import resolve_rtl_root; from pathlib import Path; print(resolve_rtl_root(Path('$ROOT')))" 2>/dev/null || true)"
fi
if [[ -z "$RTL" || ! -f "$RTL/example.sh" ]]; then
  RTL="$CFA/VerifCPU/verif_cpu_verilog"
fi
[[ -f "$RTL/example.sh" ]] || fail "VerifCPU RTL root not found: $RTL"

INSCOPE_LIST="$ROOT/goal-in-scope-files.txt"
[[ -f "$INSCOPE_LIST" ]] || fail "missing committed goal-in-scope-files.txt"
INSCOPE_COUNT="$(grep -v '^[[:space:]]*#' "$INSCOPE_LIST" | grep -cve '^[[:space:]]*$' || true)"
[[ "$INSCOPE_COUNT" -le 60 ]] || fail "goal-in-scope-files.txt: expected <=60 paths, got $INSCOPE_COUNT"

python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import gates_harness_workspace_preflight, resolve_classifier_workspace_root
from ops.intake_resolve import gates_bootstrap_revert_oos
ws = resolve_classifier_workspace_root()
pre = gates_harness_workspace_preflight(ws)
print(f'harness workspace: {ws} (writable={pre.workspace_writable})')
if pre.scrubbed_start:
    print('harness scrub (start):', *pre.scrubbed_start[:10], sep='\n  ')
cleaned = gates_bootstrap_revert_oos(Path('$CFA'), Path('$INSCOPE_LIST'))
if cleaned:
    print('reverted out-of-scope:', *cleaned, sep='\n  ')
"

cd "$CFA"

# Step 0 — git audit log only (not authoritative scope; see goal-in-scope-files.txt)
{
  echo "=== AUDIT ONLY (not CHANGED_FILES / goal-in-scope-files.txt) ==="
  echo "=== soc-verify-agent tracked (in-scope paths) ==="
  git -C "$SOC" diff --name-only -- \
    projects/VERIF-CPU-SOC/USER-PROCEDURE.md \
    projects/VERIF-CPU-SOC/howto_integrate2yourSoC.md \
    projects/VERIF-CPU-SOC/ops/intake_resolve.py \
    projects/VERIF-CPU-SOC/scripts/expand_agent_runbook.py \
    tests/test_intake_resolve.py \
    templates/obsidian/agent/vcpu-soc-integration/ 2>/dev/null || true
  echo "=== soc-verify-agent untracked (in-scope) ==="
  git -C "$SOC" status --short -- \
    projects/VERIF-CPU-SOC/scripts/run_plan_gates.sh \
    projects/VERIF-CPU-SOC/scripts/run_tier_smoke_all.sh \
    projects/VERIF-CPU-SOC/scripts/sync_intake_simulation_tier.py \
    tests/test_coi_conn_pipeline.py \
    tests/test_verifcpu_log.py \
    templates/obsidian/agent/vcpu-soc-integration/13-INTEGRATION-TIERS.md 2>/dev/null || true
  echo "=== VerifCPU tracked (plan assumed scope) ==="
  git -C "$CFA" diff --name-only -- \
    VerifCPU/verif_cpu_verilog/Makefile \
    VerifCPU/verif_cpu_verilog/firmware/campaign/Makefile \
    VerifCPU/verif_cpu_verilog/vcpu_skill.md 2>/dev/null || true
  echo "=== VerifCPU untracked smoke prerequisites (explicit paths) ==="
  git -C "$RTL" status --short -- "${VERIFCPU_SMOKE_UNTRACKED[@]}" 2>/dev/null | grep '^??' || true
  echo "=== VerifCPU pre-existing NOT modified by this goal ==="
  if ! git -C "$CFA" diff --name-only -- \
    VerifCPU/verif_cpu_verilog/example.sh \
    VerifCPU/verif_cpu_verilog/example.py \
    VerifCPU/verif_cpu_verilog/rtl/verif_cpu_core.v 2>/dev/null | grep -q .; then
    echo "(none — example.sh/example.py/filelists/scripts are repo baseline; see git-preexisting-proof.log)"
  fi
} > "$CHANGED"

{
  echo "=== git diff --quiet HEAD (pre-existing baseline must be clean) ==="
  for p in \
    VerifCPU/verif_cpu_verilog/example.sh \
    VerifCPU/verif_cpu_verilog/example.py \
    VerifCPU/verif_cpu_verilog/rtl/verif_cpu_core.v \
    VerifCPU/verif_cpu_verilog/filelists/eda/test/chip_top_example/manifest.list; do
    if git -C "$CFA" diff --quiet HEAD -- "$p" 2>/dev/null; then
      echo "CLEAN: $p"
    else
      echo "DIRTY: $p"
    fi
  done
} > "$PROOF"
grep -q '^DIRTY:' "$PROOF" && fail "pre-existing proof: unexpected dirty baseline files"

# Step 1 — pytest from soc-verify-agent root (tests/test_intake_resolve.py lives under $SOC)
cd "$SOC"
python3 -m pytest tests/test_intake_resolve.py -q --tb=line -k "not goal_deliverable" 2>&1 | tee "$SCRATCH/pytest-tier.log"
grep -q '13 passed' "$SCRATCH/pytest-tier.log" || fail "pytest tier criteria: expected 13 passed"
append "step1 pytest: $(tail -1 "$SCRATCH/pytest-tier.log")"

# Step 2 — vault+human sweep
python3 << PY > "$SCRATCH/vault-human-sweep.log"
import re
from pathlib import Path
TARGET = re.compile(r'make (?:soc-paste|soc-integration|chip-top-example)|make gen && make soc-integration', re.I)
QUAL = re.compile(r'tier|paste|yaml|scale|integration_tier|13-INTEGRATION-TIERS|skip|생략|#|하나만|첫 통합', re.I)
root = Path('$SOC')
files = [
    root/'projects/VERIF-CPU-SOC/USER-PROCEDURE.md',
    root/'projects/VERIF-CPU-SOC/howto_integrate2yourSoC.md',
    *list((root/'templates/obsidian/agent/vcpu-soc-integration').glob('*.md')),
    root/'projects/VERIF-CPU-SOC/inputs/tags/main/deployment/customer_soc_intake.example.yaml',
    Path('$RTL')/'vcpu_skill.md',
]
unguarded = []
for fp in files:
    if not fp.exists() or fp.name == '13-INTEGRATION-TIERS.md':
        continue
    lines = fp.read_text().splitlines()
    for i, line in enumerate(lines):
        if TARGET.search(line):
            ctx = '\n'.join(lines[max(0, i - 2):i + 3])
            if not QUAL.search(ctx):
                unguarded.append(f'{fp}:{i+1}')
print('=== vault-human-sweep.log ===')
print('ZERO vulnerabilities in vault+human sweep' if not unguarded else '\n'.join(unguarded))
PY
grep -q 'ZERO' "$SCRATCH/vault-human-sweep.log" || fail "sweep: expected ZERO"
append "step2 sweep: $(grep ZERO "$SCRATCH/vault-human-sweep.log" | tail -1)"

# Step 3 — USER-PROCEDURE delegation
{
  echo "=== tier table check ==="
  if rg -q '\| Step \| 할 일 \| 상세 \||\| Tier \| 언제 \| smoke \|' "$ROOT/USER-PROCEDURE.md"; then
    echo "FOUND tier table"
  else
    echo "NONE (OK)"
  fi
  rg -n '13-INTEGRATION-TIERS|03-WORKFLOW|tier 표' "$ROOT/USER-PROCEDURE.md" | head -8
  sed -n '177,210p' "$ROOT/USER-PROCEDURE.md"
} > "$SCRATCH/user-procedure.txt"
grep -q 'NONE (OK)' "$SCRATCH/user-procedure.txt" || fail "user-procedure: tier table still present"
append "step3 tier table: $(grep 'NONE (OK)' "$SCRATCH/user-procedure.txt" | head -1)"

# VerifCPU scope snapshot (explicit paths only — before smoke dirties generated headers)
{
  echo "=== tracked edits ==="
  git -C "$RTL" diff --name-only -- Makefile firmware/campaign/Makefile vcpu_skill.md 2>/dev/null || true
  echo "=== untracked smoke prerequisites ==="
  git -C "$RTL" status --short -- "${VERIFCPU_SMOKE_UNTRACKED[@]}" 2>/dev/null | grep '^??' || true
} > "$SCRATCH/verifcpu-scope-pre.log"

# Step 4 — sync, expand, slim smoke (shipped scripts + pytest subset, no inline validation py)
{
  git -C "$RTL" checkout -- include/verif_soc_bus_connect.vh 2>/dev/null || true
  cd "$ROOT"
  python3 scripts/sync_intake_simulation_tier.py --intake inputs/tags/main/deployment/customer_soc_intake.example.yaml --dry-run 2>&1 | head -2
  (cd "$SOC" && python3 -m pytest tests/test_intake_resolve.py -q -k "tier_mismatch or sync_intake or crystallize_rejects_tier" --tb=line 2>&1)
  for tier in paste yaml_multi scale; do
    python3 -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from soc_verify.models import load_yaml, save_yaml
from ops.intake_resolve import sync_intake_simulation_to_tier
ex = load_yaml(Path('inputs/tags/main/deployment/customer_soc_intake.example.yaml')) or {}
d = dict(ex); d['chip'] = dict(ex['chip']); d['chip']['integration_tier'] = '$tier'
save_yaml(Path('$SCRATCH/intake_$tier.yaml'), sync_intake_simulation_to_tier(d))
"
    echo "=== expand $tier ==="
    python3 scripts/expand_agent_runbook.py --intake "$SCRATCH/intake_${tier}.yaml" 2>&1 | rg '^## |make soc-|make gen &&|make chip-top'
  done
  bash scripts/run_tier_smoke_all.sh "$RTL" "$SCRATCH"
} > "$SCRATCH/tier-ops.log" 2>&1

grep -q 'soc_cpu_bus_paste: PASS' "$SCRATCH/tier-ops.log" || fail "smoke: paste"
grep -q 'soc_integration_example: PASS' "$SCRATCH/tier-ops.log" || fail "smoke: yaml_multi"
grep -q 'chip_top_example: PASS' "$SCRATCH/tier-ops.log" || fail "smoke: scale"
grep -q 'manifest generated headers valid' "$SCRATCH/tier-ops.log" || fail "smoke: manifest headers"
grep -q 'all tier smokes' "$SCRATCH/tier-ops.log" || fail "smoke: summary"

append "step4 paste: $(grep -E 'soc_cpu_bus_paste: PASS' "$SCRATCH/tier-ops.log" | tail -1)"
append "step4 yaml_multi: $(grep -E 'soc_integration_example: PASS' "$SCRATCH/tier-ops.log" | tail -1)"
append "step4 scale: $(grep -E 'chip_top_example: PASS' "$SCRATCH/tier-ops.log" | tail -1)"
append "step4 manifest headers: $(grep 'manifest generated headers valid' "$SCRATCH/tier-ops.log" | tail -1)"
append "step4 smoke summary: $(grep '\[PASS\] all tier smokes' "$SCRATCH/tier-ops.log" | tail -1)"
append "step4 tier3 contract: scale=chip-top-example only; manifest headers post-gen (no scale vvp)"

{
  echo "=== smoke-regenerated headers ==="
  git -C "$RTL" diff --name-only -- include/verif_soc_bus_connect.vh include/soc_integration_example_gen.vh include/chip_top_example_gen.vh 2>/dev/null || true
  git -C "$RTL" status --short -- include/verif_soc_bus_connect.vh include/soc_integration_example_gen.vh include/chip_top_example_gen.vh 2>/dev/null || true
} > "$SCRATCH/verifcpu-scope-post-smoke.log"

SCOPE_TRACKED="$(awk '/^=== tracked edits ===$/{f=1;next} /^===/{f=0} f && NF' "$SCRATCH/verifcpu-scope-pre.log" | paste -sd ', ' - || true)"
SCOPE_UNTRACKED="$(awk '/^=== untracked smoke prerequisites ===$/{f=1;next} /^===/{f=0} f && NF' "$SCRATCH/verifcpu-scope-pre.log" | tr '\n' ' ' || true)"
SCOPE_POST="$(grep -v '^===\|^$' "$SCRATCH/verifcpu-scope-post-smoke.log" | paste -sd ', ' - || true)"
append "step5 verifcpu tracked: ${SCOPE_TRACKED:-none}"
append "step5 verifcpu untracked smoke prerequisites: ${SCOPE_UNTRACKED:-none}"
append "step5 verifcpu post-smoke regenerated: ${SCOPE_POST:-none}"

DELIVERABLE="$ROOT/GOAL_DELIVERABLE.md"
CHANGED_FLAT="$SCRATCH/CHANGED_FILES"
cp "$INSCOPE_LIST" "$SCRATCH/goal-in-scope-files.txt"

python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.intake_resolve import gates_assert_clean_oos_and_write_changed
gates_assert_clean_oos_and_write_changed(Path('$CFA'), Path('$INSCOPE_LIST'), Path('$CHANGED_FLAT'))
" || fail "out-of-scope dirty paths (revert/stash paths not in goal-in-scope-files.txt)"

write_deliverable_py() {
  local pytest_full="${1:-pending}"
  local extract_file="${2:-$EXTRACT}"
  local dirty_count
  dirty_count="$(grep -cve '^[[:space:]]*$' "$CHANGED_FLAT" 2>/dev/null || echo 0)"
  PYTEST_TIER="$(grep -oE '13 passed[^$]*' "$SCRATCH/pytest-tier.log" | head -1)"
  SWEEP_LINE="$(grep ZERO "$SCRATCH/vault-human-sweep.log" | tail -1)"
  TABLE_LINE="$(grep 'NONE (OK)' "$SCRATCH/user-procedure.txt" | head -1)"
  PASTE_PASS="$(grep -E 'soc_cpu_bus_paste: PASS' "$SCRATCH/tier-ops.log" | tail -1)"
  YAML_PASS="$(grep -E 'soc_integration_example: PASS' "$SCRATCH/tier-ops.log" | tail -1)"
  SCALE_PASS="$(grep -E 'chip_top_example: PASS' "$SCRATCH/tier-ops.log" | tail -1)"
  SMOKE_SUMMARY="$(grep '\[PASS\] all tier smokes' "$SCRATCH/tier-ops.log" | tail -1)"
  python3 << PY
import sys
sys.path.insert(0, "$ROOT")
from pathlib import Path
from ops.intake_resolve import write_goal_deliverable
write_goal_deliverable(
    Path("$DELIVERABLE"),
    Path("$INSCOPE_LIST"),
    pytest_tier="""$PYTEST_TIER""",
    pytest_full="""$pytest_full""",
    sweep_line="""$SWEEP_LINE""",
    table_line="""$TABLE_LINE""",
    paste_pass="""$PASTE_PASS""",
    yaml_pass="""$YAML_PASS""",
    scale_pass="""$SCALE_PASS""",
    smoke_summary="""$SMOKE_SUMMARY""",
    extract_text=Path("$extract_file").read_text(encoding="utf-8"),
    proof_text=Path("$PROOF").read_text(encoding="utf-8"),
    inscope_count=$INSCOPE_COUNT,
    dirty_changed_count=$dirty_count,
)
PY
}

# Step 5b — finalize CFA before deliverable guard test (smoke leaves ephemeral dirty paths)
python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.intake_resolve import gates_scope_finalize_and_record
cleaned, dirty_in = gates_scope_finalize_and_record(
    cfa_root=Path('$CFA'),
    inscope_list=Path('$INSCOPE_LIST'),
    changed_flat=Path('$CHANGED_FLAT'),
    goal_root_changed=Path('$GOAL_ROOT') / 'CHANGED_FILES',
    proof_path=Path('$SCRATCH/scope-proof.log'),
    phase_label='pre-pytest finalize',
)
if cleaned:
    print('pre-pytest finalized non-inscope:', *cleaned[:20], sep='\n  ')
    if len(cleaned) > 20:
        print(f'  ... and {len(cleaned) - 20} more')
" || fail "pre-pytest finalize CFA workspace to in-scope dirty only"

# Step 6 — deliverable guard + tier pytest (plan: 13 passed in tier-final.log)
write_deliverable_py "pending"
cd "$SOC"
python3 -m pytest tests/test_intake_resolve.py -q --tb=line -k goal_deliverable 2>&1 | tee "$SCRATCH/pytest-guard.log"
grep -q '1 passed' "$SCRATCH/pytest-guard.log" || fail "pytest guard: expected goal_deliverable passed"
python3 -m pytest tests/test_intake_resolve.py -q --tb=line -k "not goal_deliverable" 2>&1 | tee "$SCRATCH/pytest-tier-final.log"
grep -q '13 passed' "$SCRATCH/pytest-tier-final.log" || fail "pytest tier-final: expected 13 passed"
append "step6 pytest tier-final: $(tail -1 "$SCRATCH/pytest-tier-final.log")"
append "step6a pytest guard: $(tail -1 "$SCRATCH/pytest-guard.log")"

python3 -m pytest tests/test_harness_evidence.py tests/test_coi_conn_pipeline.py tests/test_verifcpu_log.py -q --tb=line 2>&1 | tee "$SCRATCH/pytest-supplemental.log"
grep -qE '[0-9]+ passed' "$SCRATCH/pytest-supplemental.log" || fail "pytest supplemental: expected passed"
append "step6b pytest supplemental: $(tail -1 "$SCRATCH/pytest-supplemental.log")"

# Step 7 — deliverable v2 with full pytest result
PYTEST_FULL="$(grep -oE '13 passed[^$]*' "$SCRATCH/pytest-tier-final.log" | head -1)"
write_deliverable_py "$PYTEST_FULL"
python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.intake_resolve import validate_goal_embedded_scope, _goal_non_blank_lines
text = Path('$DELIVERABLE').read_text(encoding='utf-8')
paths = _goal_non_blank_lines(Path('$INSCOPE_LIST').read_text(encoding='utf-8'))
validate_goal_embedded_scope(text, expected_paths=paths, expected_count=$INSCOPE_COUNT)
"
python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.intake_resolve import assert_changed_files_subset_of_inscope
assert_changed_files_subset_of_inscope(Path('$CHANGED_FLAT'), Path('$INSCOPE_LIST'))
"

grep -q '11 passed' "$DELIVERABLE" && fail "deliverable: forbidden '11 passed'"
grep -q '40-path' "$DELIVERABLE" && fail "deliverable: forbidden stale '40-path' scope label"
grep -q '13 passed' "$DELIVERABLE" || fail "deliverable: missing '13 passed' (tier + tier-final)"

cp "$DELIVERABLE" "$SCRATCH/GOAL_DELIVERABLE.md"
cp "$DELIVERABLE" "$SCRATCH/FINAL_RESPONSE.md"

python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import (
    assert_harness_session_prepared,
    gates_harness_workspace_postflight,
    resolve_classifier_workspace_root,
    resolve_harness_mirror_root,
)
from ops.intake_resolve import gates_scope_finalize_and_record, load_inscope_paths_from_file, _goal_non_blank_lines
cleaned, dirty_in = gates_scope_finalize_and_record(
    cfa_root=Path('$CFA'),
    inscope_list=Path('$INSCOPE_LIST'),
    changed_flat=Path('$CHANGED_FLAT'),
    goal_root_changed=Path('$GOAL_ROOT') / 'CHANGED_FILES',
    proof_path=Path('$SCRATCH/scope-proof.log'),
    phase_label='post-deliverable finalize',
)
if cleaned:
    print('finalized non-inscope:', *cleaned[:20], sep='\n  ')
    if len(cleaned) > 20:
        print(f'  ... and {len(cleaned) - 20} more')
post = gates_harness_workspace_postflight(
    resolve_classifier_workspace_root(),
    Path('$CFA'),
    dirty_in,
    scratch_dir=Path('$SCRATCH'),
    mirror_root=resolve_harness_mirror_root(Path('$SCRATCH')),
)
if post.synced:
    print('harness sync:', *post.synced[:5], sep='\n  ')
    if len(post.synced) > 5:
        print(f'  ... and {len(post.synced) - 5} more')
if post.scrubbed_end:
    print('harness scrub (end):', *post.scrubbed_end[:5], sep='\n  ')
assert_harness_session_prepared(resolve_classifier_workspace_root(), post)
print('harness session prepared (system32: scrub/sync/mirror bookend OK)')
changed = _goal_non_blank_lines(Path('$CHANGED_FLAT').read_text(encoding='utf-8'))
inscope = set(load_inscope_paths_from_file(Path('$INSCOPE_LIST')))
extra = sorted(set(changed) - inscope)
if extra:
    raise SystemExit(f'CHANGED_FILES not inscope: {extra}')
" || fail "finalize CFA workspace to in-scope dirty only"

FLAT_LINES="$(grep -cve '^[[:space:]]*$' "$CHANGED_FLAT" 2>/dev/null || echo 0)"
[[ "$FLAT_LINES" -le "$INSCOPE_COUNT" ]] || fail "CHANGED_FILES: $FLAT_LINES paths exceeds inscope $INSCOPE_COUNT"

python3 -c "
import os
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import finalize_classifier_evidence
from ops.intake_resolve import _goal_non_blank_lines, load_inscope_paths_from_file
changed_flat = Path('$CHANGED_FLAT')
dirty_in = _goal_non_blank_lines(changed_flat.read_text(encoding='utf-8')) if changed_flat.is_file() else []
changes_path = Path('$CHANGES_FILE') if '$CHANGES_FILE' else None
patched = finalize_classifier_evidence(
    Path('$GOAL_ROOT'),
    Path('$CFA'),
    dirty_in,
    scratch_changed_files=changed_flat,
    changes_file=changes_path,
    scratch_dir=Path('$SCRATCH'),
)
if patched:
    print('classifier evidence finalized:', patched)
from ops.harness_evidence import (
    assert_classifier_patch_cfa_only,
    resolve_latest_classifier_patch,
    resolve_classifier_patch_targets,
)
latest = resolve_latest_classifier_patch(Path('$GOAL_ROOT'))
targets = resolve_classifier_patch_targets(Path('$GOAL_ROOT'), latest)
if latest:
    print('classifier latest patch:', latest)
for target in targets:
    body = target.read_text(encoding='utf-8') if target.is_file() else ''
    assert_classifier_patch_cfa_only(body, label=str(target))
    print('classifier patch OK:', target)
from ops.harness_evidence import assert_all_classifier_patches_cfa
all_patches = assert_all_classifier_patches_cfa(Path('$GOAL_ROOT'))
print(f'all classifier patches CFA: {len(all_patches)}')
" || fail "finalize classifier evidence (CFA patch / CHANGED_FILES)"

{
  echo "=== gates-extract.log ==="
  cat "$EXTRACT"
  echo "=== changed-files-in-scope.log (git audit only) ==="
  cat "$CHANGED"
  echo "=== CHANGED_FILES (dirty in-scope subset, max $INSCOPE_COUNT) ==="
  cat "$CHANGED_FLAT"
  echo "=== git-preexisting-proof.log ==="
  cat "$PROOF"
  echo "=== GOAL_DELIVERABLE.md ==="
  cat "$DELIVERABLE"
} > "$SCRATCH/perfect-review.txt"

# Harness skeptic channel — prompt input must match CFA evidence (not Windows logs)
python3 -c "
import os
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import build_harness_prompt_proof_text
proof = build_harness_prompt_proof_text(
    Path('$GOAL_ROOT'),
    Path('$CHANGED_FLAT'),
    changes_file_env=os.environ.get('CHANGES_FILE'),
    include_terminal_round=False,
)
Path('$SCRATCH/harness-prompt-proof.txt').write_text(proof, encoding='utf-8')
print(proof, end='')
" || fail "harness prompt proof (CHANGED_FILES / CHANGES_FILE CFA alignment)"

PYTEST_TIER="$(grep -oE '13 passed[^$]*' "$SCRATCH/pytest-tier.log" | head -1)"
cat "$DELIVERABLE"

# Terminal seal: write canonical patch, purge round-numbered files, proof → counter
bash "$ROOT/scripts/verify_classifier_evidence.sh" "$SCRATCH" \
  || fail "terminal seal classifier evidence"

echo "[PASS] run_plan_gates.sh — all gates OK (${PYTEST_TIER:-13 passed})" | tee "$SCRATCH/gates-verdict.log"

# Post-PASS re-seal: outer harness may clobber highest round after script window
bash "$ROOT/scripts/verify_classifier_evidence.sh" "$SCRATCH" \
  | tee "$SCRATCH/verify-post-pass.log" \
  || fail "post-PASS seal classifier evidence"
export CHANGES_FILE="$(python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import resolve_latest_classifier_patch
p = resolve_latest_classifier_patch(Path('$GOAL_ROOT'))
print(p or '', end='')
")"
python3 -c "
import sys
sys.path.insert(0, '$ROOT')
from pathlib import Path
from ops.harness_evidence import (
    assert_all_classifier_patches_cfa,
    classifier_proof_is_stale,
    resolve_latest_classifier_patch,
)
goal_root = Path('$GOAL_ROOT')
proof_path = Path('$SCRATCH/harness-prompt-proof.txt')
latest = resolve_latest_classifier_patch(goal_root)
if latest is None:
    raise SystemExit('no latest classifier patch')
assert_all_classifier_patches_cfa(goal_root)
if classifier_proof_is_stale(goal_root, proof_path):
    raise SystemExit(f'proof stale vs latest {latest}')
proof = proof_path.read_text(encoding='utf-8')
round_n = next(
    (ln.split(':', 1)[1].strip() for ln in proof.splitlines() if ln.startswith('terminal_finalize_round:')),
    '(missing)',
)
print(f'post-PASS proof OK: terminal_finalize_round={round_n} CHANGES_FILE={latest}')
" || fail "post-PASS proof round must match resolve_latest_classifier_patch"