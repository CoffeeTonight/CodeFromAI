#!/usr/bin/env bash
# Cadence Xcelium xrun using split EDA lists.
# Usage: ./scripts/xcelium/xrun.sh <view>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib/eda_lists.sh
source "$ROOT/scripts/lib/eda_lists.sh"
XRUN="${XRUN:-xrun}"
VIEW="${1:-full_campaign}"

eda_require_view "$VIEW"
MANIFEST="$(eda_prefix "$VIEW")/manifest.list"
TOPFILE="$(eda_prefix "$VIEW")/top.txt"

if ! command -v "$XRUN" >/dev/null 2>&1; then
  echo "[xrun] $XRUN not in PATH — load Cadence env" >&2; exit 1
fi
TOP="${XRUN_TOP:-$(cat "$TOPFILE")}"
OUTDIR="sim_build/xcelium_${VIEW}"
mkdir -p "$OUTDIR"

echo "[xrun] view=$VIEW top=$TOP manifest=$MANIFEST"
"$XRUN" -64bit -sv -timescale 1ns/1ps \
  -F "$MANIFEST" -top "$TOP" \
  -elaborate -clean \
  -xmlibdirname "$OUTDIR/xcelium.d"
echo "[xrun] sim: cd $OUTDIR && xrun -R  (or your probe flow)"
