#!/usr/bin/env bash
# Phase 27: parse per-file diag, multi-def module_ref, gen_ifdef golden, synthetic smoke
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

echo "== phase27 unit tests =="
pytest tests/phase27/ tests/phase28/ -m "not slow" -q

echo "== synthetic filelist + parse smoke =="
python3 scripts/diagnose_tier_e_failures.py --only filelist --json-only 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); e=d['scenarios']['filelist_expand']; assert not e.get('errors'), e; print('sources', e['source_count'])"

if [[ "${HCH_SKIP_SYNTH_INDEX:-0}" != "1" ]]; then
  echo "== synthetic hybrid index (set HCH_SKIP_SYNTH_INDEX=1 to skip) =="
  OUT="${TMPDIR:-/tmp}/syn_deep_$$.hch.db"
  python3 -m hch.apps.index_cli \
    design/synthetic_deep_rtl/top_deep_soc.hc.f \
    -o "$OUT" \
    --top deep_soc_top \
    --elaborate \
    --index-cwd "$ROOT/design/synthetic_deep_rtl"
  python3 -c "
import sqlite3, json
c=sqlite3.connect('$OUT')
n=c.execute('select count(*) from instances').fetchone()[0]
md=c.execute(\"select value from meta where key='multi_def_module_count'\").fetchone()
hy=c.execute(\"select value from meta where key='hierarchy_source'\").fetchone()
print('instances', n, 'multi_def', md[0] if md else '?', 'source', hy[0] if hy else '?')
assert n > 100, n
assert hy and hy[0]=='path_elab_hybrid', hy
"
  rm -f "$OUT" "${OUT}.slang.f"
fi

echo "OK phase27+28"