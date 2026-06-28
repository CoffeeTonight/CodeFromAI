#!/usr/bin/env bash
# Post-gate self-harness: meta-collect pipeline for current RUN_ID
set -euo pipefail
source "$(dirname "$0")/_common.sh"
RUN_ID="${RUN_ID:-${1:-}}"
[[ -n "$RUN_ID" ]] || die "usage: post_gate_self_harness.sh RUN_ID"
bash "$(dirname "$0")/self_harness.sh" meta-collect VERIF-CPU-SOC "$RUN_ID"
bash "$(dirname "$0")/self_harness.sh" status VERIF-CPU-SOC "$RUN_ID"