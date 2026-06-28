#!/usr/bin/env bash
# =============================================================================
# VERIF-CPU-SOC — 전체 검증 순서 실행 (M2, tag main)
#
# 아래 3단계를 **검증했던 순서 그대로** 호출합니다. gate 옵션/분기 없음.
# 순서 정의: scripts/verification_sequence.yaml
#
# Usage:
#   ./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
#   RUN_ID_PREFIX=my-week24 ./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/_common.sh"

export RUN_ID_PREFIX="${RUN_ID_PREFIX:-verify-${TAG}-$(date +%Y%m%d)}"

log "VERIF-CPU-SOC verification sequence — tag=${TAG}"
log "RUN_ID_PREFIX=${RUN_ID_PREFIX}"
log "See: scripts/verification_sequence.yaml"
echo ""

log "========== Step 1/3: Sanity — VerifCPU c-compile & elab =========="
bash "${SCRIPT_DIR}/01_sanity_VerifCPU_c-compile_and_elab.sh"
echo ""

log "========== Step 2/3: Static COI connectivity (chip_top) =========="
bash "${SCRIPT_DIR}/02_static_COI_connectivity_chip_top.sh"
echo ""

log "========== Step 3/3: Simulation slave R/W (single / burst / cpu_sync) =========="
bash "${SCRIPT_DIR}/03_simulation_slave_R_W_single_burst_cpu_sync.sh"
echo ""

log "========== Reports =========="
bash "${SCRIPT_DIR}/99_generate_verification_reports.sh"
echo ""

log "Sequence complete."
log "Reports synced to run_id=${RUN_ID} (see reports/index.yaml)"