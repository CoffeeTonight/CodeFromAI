#!/usr/bin/env bash
# Cadence Xcelium xrun using split EDA lists.
# Usage: ./scripts/xcelium/xrun.sh <view>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
XRUN="${XRUN:-xrun}"
VIEW="${1:-full_campaign}"

MANIFEST="$(eda_prefix "$VIEW")/manifest.list"
TOPFILE="filelists/eda/${VIEW}/top.txt"

if ! command -v "$XRUN" >/dev/null 2>&1; then
  echo "[xrun] $XRUN not in PATH — load Cadence env" >&2; exit 1
fi
[[ -f "$MANIFEST" ]] || {
  echo "[xrun] missing $MANIFEST — run: ./example.sh gen" >&2
  echo "  views: integration full_campaign soc_manifest soc_manifest_scale chip_top_example" >&2
  exit 1
}
TOP="${XRUN_TOP:-$(cat "$TOPFILE")}"
OUTDIR="sim_build/xcelium_${VIEW}"
mkdir -p "$OUTDIR"

echo "[xrun] view=$VIEW top=$TOP lists=filelists/eda/$VIEW/{vcpu,rtl,tb_top}.list"
"$XRUN" -64bit -sv -timescale 1ns/1ps \
  -F "$MANIFEST" -top "$TOP" \
  -elaborate -clean \
  -xmlibdirname "$OUTDIR/xcelium.d"
echo "[xrun] sim: cd $OUTDIR && xrun -R  (or your probe flow)"
