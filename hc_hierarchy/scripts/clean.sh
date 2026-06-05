#!/usr/bin/env bash
# Cross-platform wrapper — prefer: python3 scripts/clean.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 "$ROOT/scripts/clean.py" "$@"