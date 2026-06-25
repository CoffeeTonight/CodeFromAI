#!/usr/bin/env bash
# VCS compile using split EDA lists (vcpu / rtl / tb_top).
# Usage: ./scripts/vcs/compile.sh <view>   OR   ./scripts/vcs/compile.sh eda <view>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VCS="${VCS:-vcs}"
MODE="${1:-full_campaign}"
VIEW="${2:-}"

if [[ "$MODE" == "eda" ]]; then
  VIEW="${2:-full_campaign}"
else
  VIEW="$MODE"
fi

MANIFEST="$(eda_prefix "$VIEW")/manifest.list"
TOPFILE="filelists/eda/${VIEW}/top.txt"

if ! command -v "$VCS" >/dev/null 2>&1; then
  echo "[vcs] $VCS not in PATH" >&2; exit 1
fi
[[ -f "$MANIFEST" ]] || {
  echo "[vcs] missing $MANIFEST — run: ./example.sh gen" >&2
  echo "  views: integration full_campaign soc_manifest soc_manifest_scale chip_top_example" >&2
  exit 1
}
TOP="${VERDI_TOP:-$(cat "$TOPFILE")}"
OUTDIR="sim_build/vcs_${VIEW}"
mkdir -p "$OUTDIR"

echo "[vcs] view=$VIEW top=$TOP lists=filelists/eda/$VIEW/{vcpu,rtl,tb_top}.list"
"$VCS" -sverilog -full64 -kdb -debug_access+all \
  -F "$MANIFEST" -top "$TOP" \
  -o "$OUTDIR/simv" -Mdir="$OUTDIR/csrc"
echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir"
