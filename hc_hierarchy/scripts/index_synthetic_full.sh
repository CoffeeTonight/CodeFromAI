#!/usr/bin/env bash
# Full synthetic_deep_rtl index with checkpoint batches (resume-safe)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FL="$ROOT/design/synthetic_deep_rtl/top_deep_soc.hc.f"
DB="${1:-$ROOT/design/synthetic_deep_rtl/deep_soc.hch.db}"
exec hch-index "$FL" -o "$DB" --top deep_soc_top --batch-size 64 --resume "$@"