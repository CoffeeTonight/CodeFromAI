#!/usr/bin/env bash
# goal_build_id = 12 — sync baseline min_unit_tests with plan.md literals atomically
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLAN="${SOCVERIF_GOAL_PLAN:-/home/user/.grok/sessions/%2Fhome%2Fuser/019f0539-43e8-76f0-a3ec-b6a269d83593/goal/plan.md}"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
cd "$ROOT"

MIN=$(python3 -c "from socverif.baseline import load_baseline; print(load_baseline()['min_unit_tests'])")
echo "sync_baseline_literals: minimum=$MIN"

python3 -c "
import re
from pathlib import Path
plan = Path('${PLAN}')
if not plan.is_file():
    raise SystemExit('plan.md missing')
text = plan.read_text(encoding='utf-8')
minimum = int('${MIN}')
patterns = [
    (r'unittest=\d+', f'unittest={minimum}'),
    (r'Ran \d+ tests', f'Ran {minimum} tests'),
    (r'min_unit_tests==\d+', f'min_unit_tests=={minimum}'),
    (r'confirm \d+\)', f'confirm {minimum})'),
]
for pat, repl in patterns:
    text = re.sub(pat, repl, text)
plan.write_text(text, encoding='utf-8')
print('updated', plan)
"