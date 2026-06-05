#!/usr/bin/env bash
# Full synthetic_deep_rtl: batched index + batch DQL (slow; ~3–10 min by machine).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FL="$ROOT/design/synthetic_deep_rtl/top_deep_soc.hc.f"
DB="${1:-$ROOT/design/synthetic_deep_rtl/deep_soc.hch.db}"
BATCH="$ROOT/fixtures/dql_batch_synthetic_full.txt"
OUT="${2:-$ROOT/design/synthetic_deep_rtl/full_batch.tsv}"

if ! python3 -c "import pyslang" 2>/dev/null; then
  echo "SKIP: pyslang not installed"
  exit 0
fi

if [[ ! -f "$FL" ]]; then
  echo "ERROR: missing $FL"
  exit 1
fi

echo "=== Full synthetic: index (batch-size 64, resume) ==="
echo "DB: $DB"
hch-index "$FL" -o "$DB" --top deep_soc_top --batch-size 64 --resume

echo "=== Full synthetic: batch DQL ==="
hch-query "$BATCH" -d "$DB" -o "$OUT"
echo "Wrote $OUT"
echo "=== Full batch DQL OK ==="