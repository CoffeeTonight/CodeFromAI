#!/usr/bin/env bash
# VerifCPU Verilog model — generate firmware artifacts and run authoritative campaign.
#
# Usage:
#   ./example.sh              # gen + full_campaign (default)
#   ./example.sh gen          # generation only (no iverilog)
#   ./example.sh sim          # simulate only (assumes fw already built)
#   ./example.sh vcd          # verify existing VCD artifacts
#   ./example.sh clean        # remove all verification artifacts
#   ./example.sh help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FW="${ROOT}/firmware/campaign"
LOG_FULL="${LOG_FULL:-${ROOT}/logs/full_campaign}"
VCD_MAIN="${ROOT}/sim_build/tb_full_campaign.vcd"

die() { echo "[example.sh] ERROR: $*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

step() {
  echo ""
  echo "========================================================================"
  echo "$1"
  echo "========================================================================"
}

run_gen() {
  step "[1/2] Generate campaign firmware + Verilog headers"
  [[ -d "$FW" ]] || die "firmware dir not found: $FW"
  need_cmd python3

  cd "$FW"
  echo "[gen] soc_init  → soc_init_seq.vh, campaign_soc_platform.vh"
  make soc_init

  echo "[gen] manifest  → campaign_manifest.vh"
  make manifest

  echo "[gen] icodes    → icode_pool.bin, icode_map.vh, tb_full_campaign_gen.vh"
  make icodes

  echo "[gen] VCPU bins + merge → full_campaign_unified.hex"
  make all

  echo ""
  echo "[gen] Artifacts:"
  ls -la build/*.bin 2>/dev/null || true
  ls -la "${ROOT}/firmware/"*.hex 2>/dev/null || true
  ls -la "${ROOT}/include/tb_full_campaign_gen.vh" \
         "${ROOT}/include/icode_map.vh" \
         "${ROOT}/include/campaign_manifest.vh" 2>/dev/null || true
}

run_sim() {
  step "[2/2] iverilog full_campaign (authoritative gate)"
  need_cmd iverilog
  need_cmd vvp
  need_cmd python3

  cd "$ROOT"
  mkdir -p "$LOG_FULL"
  make full_campaign

  echo ""
  echo "[sim] VCD artifacts:"
  echo "  Main : $VCD_MAIN"
  for cid in 1 2 3; do
    p="${LOG_FULL}/SCPU${cid}.vcd"
    if [[ -f "$p" ]]; then
      echo "  CPU${cid}: $p ($(wc -c < "$p") bytes)"
    fi
  done
}

run_vcd_only() {
  step "VCD post-check (verify_vcd.py)"
  need_cmd python3
  [[ -f "$VCD_MAIN" ]] || die "missing main VCD: $VCD_MAIN (run ./example.sh sim first)"

  python3 "${ROOT}/tools/verify_vcd.py" \
    "$VCD_MAIN" \
    "${LOG_FULL}/SCPU1.vcd" \
    "${LOG_FULL}/SCPU2.vcd" \
    "${LOG_FULL}/SCPU3.vcd"
}

run_clean() {
  step "Clean verification artifacts (sim_build, logs, campaign build)"
  cd "$ROOT"
  make clean-artifacts
  echo "[clean] done — regenerate with: ./example.sh gen"
}

show_help() {
  cat <<'EOF'
VerifCPU Verilog example runner

Commands:
  (none)|all   Generate firmware + run full_campaign + VCD gate
  gen          Generation only (firmware/campaign make pipeline)
  sim          Simulation only (make full_campaign; rebuilds fw via Makefile)
  vcd          Re-run verify_vcd.py on existing VCD files
  clean        Remove sim_build, logs, campaign build, merged hex
  help         Show this message

Environment:
  LOG_FULL     Per-CPU VCD log directory (default: .../VerifCPU/logs/full_campaign)

Examples:
  ./example.sh
  ./example.sh gen && ./example.sh sim
  LOG_FULL=/tmp/vcd ./example.sh sim
EOF
}

main() {
  local cmd="${1:-all}"
  case "$cmd" in
    all|full|verify)
      run_gen
      run_sim
      ;;
    gen|generate)
      run_gen
      ;;
    sim|run|simulate)
      run_sim
      ;;
    vcd|check-vcd)
      run_vcd_only
      ;;
    clean)
      run_clean
      ;;
    help|-h|--help)
      show_help
      ;;
    *)
      die "unknown command: $cmd (try: ./example.sh help)"
      ;;
  esac
}

main "$@"