#!/usr/bin/env bash
# VCS compile using split EDA lists (vcpu / rtl / tb_top).
# Usage: ./scripts/vcs/compile.sh <view>   OR   ./scripts/vcs/compile.sh eda <view>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib/eda_lists.sh
source "$ROOT/scripts/lib/eda_lists.sh"
VCS="${VCS:-vcs}"
MODE="${1:-full_campaign}"
VIEW="${2:-}"

if [[ "$MODE" == "eda" ]]; then
  VIEW="${2:-full_campaign}"
else
  VIEW="$MODE"
fi

eda_require_view "$VIEW"
MANIFEST="$(eda_prefix "$VIEW")/manifest.list"
TOPFILE="$(eda_prefix "$VIEW")/top.txt"

if ! command -v "$VCS" >/dev/null 2>&1; then
  echo "[vcs] $VCS not in PATH" >&2; exit 1
fi
TOP="${VERDI_TOP:-$(cat "$TOPFILE")}"
OUTDIR="sim_build/vcs_${VIEW}"
mkdir -p "$OUTDIR"

echo "[vcs] view=$VIEW top=$TOP manifest=$MANIFEST"
"$VCS" -sverilog -full64 -kdb -debug_access+all -timescale=1ns/1ps \
  -F "$MANIFEST" -top "$TOP" \
  -o "$OUTDIR/simv" -Mdir="$OUTDIR/csrc"
echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir"
