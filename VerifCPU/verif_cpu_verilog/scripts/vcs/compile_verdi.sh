#!/usr/bin/env bash
# Deprecated alias — use ./scripts/vcs/compile.sh <view>
# Kept so old docs/scripts that call compile_verdi.sh still work.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "[vcs] compile_verdi.sh is deprecated; forwarding to compile.sh" >&2
exec "$ROOT/scripts/vcs/compile.sh" "$@"
