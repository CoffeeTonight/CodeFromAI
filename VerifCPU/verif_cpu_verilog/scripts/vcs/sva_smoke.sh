#!/usr/bin/env bash
# Optional commercial compile of AXI handshake SVA + smoke TB.
# Usage (from verif_cpu_verilog/): ./scripts/vcs/sva_smoke.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
VCS="${VCS:-vcs}"
if ! command -v "$VCS" >/dev/null 2>&1; then
  echo "[sva] $VCS not in PATH — skip (use: make soc-bus-sva for iverilog mon path)"
  exit 0
fi
OUTDIR=sim_build/vcs_sva_smoke
mkdir -p "$OUTDIR"
echo "[sva] compiling with +define+VERIF_BUS_SVA"
"$VCS" -sverilog -full64 -timescale=1ns/1ps \
  +define+VERIF_BUS_SVA \
  +incdir+include \
  sva/verif_axi_hs_sva.sv \
  rtl/verif_axi_full_master.v rtl/verif_axi_full_slave_simple.v \
  tb/tb_axi_sva_smoke.v \
  -top tb_axi_sva_smoke \
  -o "$OUTDIR/simv" -Mdir="$OUTDIR/csrc"
echo "[sva] run $OUTDIR/simv"
"$OUTDIR/simv"
