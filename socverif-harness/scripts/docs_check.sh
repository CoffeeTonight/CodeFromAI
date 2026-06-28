#!/usr/bin/env bash
# goal_build_id = 12 — verification plan step 1: full doc keyword gate (real exit codes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="${SCRATCH:-$ROOT/.socverif/scratch}"
OUT="${1:-$SCRATCH/docs_check.log}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT"

FAILED=0
exec 3>&1
{
  echo "=== docs_check $(date -Iseconds) ==="
  for f in eda_tool.md soc_validation_flow.md success_flow.md failed_flow.md; do
    echo "--- docs/$f ($(wc -l < "docs/$f") lines) ---"
    head -3 "docs/$f"
  done
  echo ""
  echo "=== required keyword grep ==="
  for term in \
    "header 컴파일" "C코드 수정" "SFR내 bit field" "fw compile" \
    "vcd dump할 신호" "RTL compile" "재검증 진행법" "{검증방법name}.md" \
    "toy_mimic_soc" "TAT가 대단히 짧은" "LLM이 돌릴수있는" \
    "toy-create" "toy_creator" \
    "5.9s" "rc=127" "resolve_project_root" "reference_envs" "nightly" \
    "toy_policy" "SELF_HARNESS_REPEAT" "SELF_HARNESS_CAPABILITY" "workspace_delta" "preflight_final_claims"
  do
    echo -n "  [$term] "
    hits=$(rg -l -F "$term" docs/ README.md socverif/ scripts/ 2>/dev/null | tr '\n' ' ' || true)
    if [[ -z "${hits// }" ]]; then
      echo "MISSING"
      FAILED=1
    else
      echo "$hits"
    fi
  done
  echo ""
  echo "=== toy_mimic_soc template ==="
  if [[ -f envs/toy_mimic_soc/.socverif/toy_mimic.yaml && -f envs/toy_mimic_soc/Makefile ]]; then
    echo "OK toy_mimic_soc template"
  else
    echo "MISSING toy_mimic_soc template"
    FAILED=1
  fi
  echo ""
  echo "=== required socverif modules ==="
  for mod in cli.py runner.py vlp.py manifest.py constants.py; do
    echo -n "  [socverif/$mod] "
    if [[ -f "socverif/$mod" ]]; then
      echo "OK"
    else
      echo "MISSING"
      FAILED=1
    fi
  done
  echo ""
  echo "=== user_methods merge gate ==="
  python3 -m socverif.user_methods --json
} > >(tee "$OUT" >&3)
wait
if grep -qE 'MISSING (toy_mimic_soc|socverif/)' "$OUT" 2>/dev/null; then
  FAILED=1
fi

if ! python3 -m socverif.user_methods --json >/dev/null; then
  echo "docs_check: user_methods FAILED" >&2
  exit 1
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo "docs_check: keyword MISSING" >&2
  exit 1
fi

echo "USER_METHODS_CHECK_PASS" | tee -a "$OUT"
echo "DOCS_CHECK_PASS" | tee -a "$OUT"