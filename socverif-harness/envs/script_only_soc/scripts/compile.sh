#!/usr/bin/env bash
# goal_build_id = 12
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p build logs
iverilog -g2012 -I rtl -I tb -o build/chip.vvp rtl/periph_soc.v tb/tb_script_soc.v