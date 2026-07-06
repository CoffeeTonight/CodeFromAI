#!/usr/bin/env bash
# Verilator — compile + run (example flow; authoritative gate is iverilog).
# Usage: ./scripts/verilator/run.sh [view]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib/eda_lists.sh
source "$ROOT/scripts/lib/eda_lists.sh"

VIEW="${1:-full_campaign}"
VERILATOR="${VERILATOR:-verilator}"

eda_require_view "$VIEW"
TOP="${VERILATOR_TOP:-$(eda_top "$VIEW")}"
OUTDIR="sim_build/verilator_${VIEW}"
mkdir -p "$OUTDIR"

if ! command -v "$VERILATOR" >/dev/null 2>&1; then
  echo "[verilator] $VERILATOR not in PATH" >&2; exit 1
fi

mapfile -t SOURCES < <(eda_source_files "$VIEW")
if [[ ${#SOURCES[@]} -eq 0 ]]; then
  echo "[verilator] no sources for view=$VIEW" >&2; exit 1
fi

TRACE_ARGS=()
if [[ "${VERILATOR_TRACE:-1}" == "1" ]]; then
  TRACE_ARGS=(--trace-vcd)
fi

read -r -a VLT_INCDIRS <<< "$(eda_verilator_incdirs "$VIEW")"
read -r -a VLT_DEFINES <<< "$(eda_verilator_defines "$VIEW")"
echo "[verilator] view=$VIEW top=$TOP sources=${#SOURCES[@]} → $OUTDIR"
"$VERILATOR" --binary -j 0 --timing \
  "${VLT_INCDIRS[@]}" \
  "${VLT_DEFINES[@]}" \
  --top-module "$TOP" \
  -Wno-fatal -Wno-WIDTH -Wno-UNOPTFLAT -Wno-STMTDLY -Wno-DECLFILENAME \
  -Mdir "$OUTDIR" "${TRACE_ARGS[@]}" "${SOURCES[@]}"

EXE="$OUTDIR/V$TOP"
if [[ ! -x "$EXE" ]]; then
  echo "[verilator] missing executable $EXE" >&2; exit 1
fi
echo "[verilator] run $EXE"
"$EXE"
if [[ "${VERILATOR_TRACE:-1}" == "1" ]]; then
  echo "[verilator] VCD trace under $OUTDIR/ (verilator --trace-vcd)"
fi
