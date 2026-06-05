#!/usr/bin/env bash
# Verify batch DQL on hc_hierarchy dummy designs (HDLforAST + synthetic quick).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== hc_hierarchy batch DQL verify ==="

HDL_FL="$ROOT/design/HDLforAST/filelist.f"
QUICK_FL="$ROOT/design/synthetic_deep_rtl/quick.hc.f"
OUT_DIR="${TMPDIR:-/tmp}/hch_batch_verify_$$"
mkdir -p "$OUT_DIR"

if ! python3 -c "import pyslang" 2>/dev/null; then
  echo "SKIP: pyslang not installed (pip install -e '.[engine]')"
  exit 0
fi

# --- HDLforAST ---
if [[ -f "$HDL_FL" ]]; then
  echo "--- Index HDLforAST ---"
  python3 -m hch.apps.index_cli "$HDL_FL" -o "$OUT_DIR/hdlforast.hch.db" --top top_module
  echo "--- Batch query HDLforAST ---"
  python3 -m hch.apps.query_cli "$ROOT/fixtures/dql_batch_hdlforast.txt" \
    -d "$OUT_DIR/hdlforast.hch.db" -o "$OUT_DIR/hdlforast_batch.tsv"
  echo "HDLforAST batch: OK -> $OUT_DIR/hdlforast_batch.tsv"
else
  echo "WARN: missing $HDL_FL"
fi

# --- synthetic_deep_rtl quick ---
if [[ -f "$QUICK_FL" ]]; then
  echo "--- Index synthetic quick ---"
  python3 -m hch.apps.index_cli "$QUICK_FL" -o "$OUT_DIR/quick.hch.db" --top deep_soc_top
  echo "--- Batch query synthetic quick ---"
  python3 -m hch.apps.query_cli "$ROOT/fixtures/dql_batch_synthetic_quick.txt" \
    -d "$OUT_DIR/quick.hch.db" -o "$OUT_DIR/quick_batch.tsv"
  echo "synthetic quick batch: OK -> $OUT_DIR/quick_batch.tsv"
else
  echo "WARN: missing $QUICK_FL"
fi

echo "=== Fast batch checks passed ==="
echo "For full synthetic (~991 sources): ./scripts/verify_batch_dql_full.sh"