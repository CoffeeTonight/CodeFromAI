#!/usr/bin/env bash
# goal_build_id = 12
# Loop all reference envs — proves generic adapter works across layouts
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

fail=0
for env in toy_mimic_soc minimal_soc alt_soc synthetic_vcs_style script_only_soc; do
  echo ""
  echo "################################################################"
  echo "# ENV: $env"
  echo "################################################################"
  if python3 -m socverif.cli loop "${ROOT}/envs/${env}" --max-tier 3; then
    echo "[OK] $env"
  else
    echo "[FAIL] $env"
    fail=1
  fi
done
exit $fail