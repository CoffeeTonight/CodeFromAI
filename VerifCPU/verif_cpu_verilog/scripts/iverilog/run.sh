#!/usr/bin/env bash
# Icarus Verilog — compile + run using filelists/eda/<view>/*.list
# Usage: ./scripts/iverilog/run.sh [view]
# Example: ./scripts/iverilog/run.sh full_campaign
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib/eda_lists.sh
source "$ROOT/scripts/lib/eda_lists.sh"

VIEW="${1:-full_campaign}"
IVERILOG="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"

eda_require_view "$VIEW"
TOP="${IVERILOG_TOP:-$(eda_top "$VIEW")}"
OUTDIR="sim_build/iverilog_${VIEW}"
VVP_OUT="$OUTDIR/sim.vvp"
mkdir -p "$OUTDIR"

if ! eda_has_tb "$VIEW"; then
  echo "[iverilog] view=$VIEW has no TB — use integration flow or pick another view" >&2
  exit 1
fi

if ! command -v "$IVERILOG" >/dev/null 2>&1; then
  echo "[iverilog] $IVERILOG not in PATH" >&2; exit 1
fi
if ! command -v "$VVP" >/dev/null 2>&1; then
  echo "[iverilog] $VVP not in PATH" >&2; exit 1
fi

VCD="$(eda_vcd "$VIEW")"
if [[ -n "$VCD" ]]; then mkdir -p "$(dirname "$VCD")"; fi

echo "[iverilog] view=$VIEW top=$TOP → $VVP_OUT"
read -r -a IV_FLAGS <<< "$(eda_iverilog_f_flags "$VIEW")"
"$IVERILOG" -g2012 "${IV_FLAGS[@]}" -s "$TOP" -o "$VVP_OUT"
echo "[iverilog] vvp $VVP_OUT"
"$VVP" "$VVP_OUT"
if [[ -n "$VCD" && -f "$VCD" ]]; then
  echo "[iverilog] VCD: $VCD"
fi
