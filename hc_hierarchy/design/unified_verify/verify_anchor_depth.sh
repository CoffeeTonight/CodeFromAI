#!/usr/bin/env bash
# depth-anchor-module *_top + extra 2 — index, DQL, pytest (Termux-friendly)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DESIGN="$(cd "$(dirname "$0")" && pwd)"
DB="${DB:-$DESIGN/unified_anchor.hch.db}"
export PYTHONPATH="${ROOT}/src"
cd "$ROOT"

_run_index() {
  echo "== index -> $DB =="
  rm -f "$DB"
  python3 -m hch.apps.index_cli \
    "$DESIGN/filelist.f" \
    -o "$DB" \
    --top hc_verify_top \
    --index-cwd "$DESIGN" \
    --depth-anchor-module '*_top' \
    --depth-anchor-extra 2 \
    --depth-shallow 2 \
    --blackbox-path hfa \
    -j "${JOBS:-4}" \
    --batch-size 64
}

_run_query() {
  echo "== query flat chain =="
  python3 -m hch.apps.query_cli -d "$DB" \
    -q 'path ^= "hc_verify_top.u_anchor_flat"' --text

  echo "== query nested chain =="
  python3 -m hch.apps.query_cli -d "$DB" \
    -q 'path ^= "hc_verify_top.u_anchor_nested"' --text

  echo "== query D3 absent (flat) =="
  python3 -m hch.apps.query_cli -d "$DB" \
    -q 'path = "hc_verify_top.u_anchor_flat.u_chain.u_d2.u_d3"' --text || true

  echo "== query D3 absent (nested) =="
  python3 -m hch.apps.query_cli -d "$DB" \
    -q 'path = "hc_verify_top.u_anchor_nested.u_inner.u_chain.u_d2.u_d3"' --text || true
}

_run_test() {
  echo "== pytest =="
  pytest tests/phase29/test_anchor_depth_unified.py -q
}

usage() {
  echo "Usage: $0 [all|index|query|test]"
  echo "  DB=$DB"
  echo "  JOBS=${JOBS:-4} (index parallelism)"
}

cmd="${1:-all}"
case "$cmd" in
  index) _run_index ;;
  query) _run_query ;;
  test)  _run_test ;;
  all)
    _run_index
    _run_query
    _run_test
    echo "OK anchor depth verify"
    ;;
  -h|--help) usage ;;
  *) usage; exit 1 ;;
esac