#!/usr/bin/env bash
set -euo pipefail
mkdir -p build
iverilog -o build/chip.vvp rtl/dut.v tb/tb.v