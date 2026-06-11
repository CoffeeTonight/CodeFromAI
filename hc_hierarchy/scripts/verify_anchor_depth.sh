#!/usr/bin/env bash
# Wrapper: run design/unified_verify/verify_anchor_depth.sh from repo root
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/design/unified_verify/verify_anchor_depth.sh" "$@"