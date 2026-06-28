#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
vvp build/chip.vvp -l logs/tier0.log