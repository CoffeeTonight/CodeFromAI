#!/usr/bin/env bash
# VerifCPU Verilog model — generate firmware artifacts and run authoritative campaign.
#
# Usage:
#   ./example.sh              # gen + full_campaign (default)
#   ./example.sh gen 64
#   ./example.sh gen --axi 62 --ahb 1 --apb 1   # bus layout: order = slot order from SCPU1
#   ./example.sh gen --apb 1 --axi 62 --ahb 1   # APB at SCPU1, then AXI, then AHB
#   ./example.sh all 64       # gen 64 + full_campaign
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

ensure_py_deps() {
  local req="${ROOT}/requirements.txt"
  [[ -f "$req" ]] || die "missing $req"
  need_cmd python3
  echo "[deps] python3 -m pip install -r requirements.txt (tinyrv, PyYAML)"
  python3 -m pip install -r "$req"
}

step() {
  echo ""
  echo "========================================================================"
  echo "$1"
  echo "========================================================================"
}

parse_num_scpu() {
  local arg="${1:-}"
  [[ -z "$arg" ]] && return 0
  if [[ ! "$arg" =~ ^[0-9]+$ ]]; then
    die "invalid slave SCPU count: '$arg' (use: ./example.sh gen 64)"
  fi
  if (( arg < 0 || arg > 256 )); then
    die "NUM_SCPU out of range: $arg (allowed 0..256; 0 = solo MVCPU)"
  fi
  export NUM_SCPU="$arg"
  echo "[example.sh] CAMPAIGN_NUM_SCPU=${NUM_SCPU}"
}

# Ordered bus layout: flag order = ascending cpu_id (SCPU1 first).
# Canonical bus keys: amba_bus_registry.py (apb3, ahb_lite, axi4lite, niu, …)
is_bus_layout_flag() {
  (cd "$FW" && python3 -c "from amba_bus_registry import CLI_FLAG_TO_BUS; import sys; raise SystemExit(0 if sys.argv[1] in CLI_FLAG_TO_BUS else 1)" "$1")
}

bus_kind_from_flag() {
  (cd "$FW" && python3 -c "from amba_bus_registry import CLI_FLAG_TO_BUS; import sys; print(CLI_FLAG_TO_BUS[sys.argv[1]])" "$1")
}

parse_gen_args() {
  local layout=""
  local layout_total=0
  local positional=""
  local a count kind

  while (( $# > 0 )); do
    a="$1"
    if is_bus_layout_flag "$a"; then
      count="${2:-}"
      [[ -n "$count" && "$count" =~ ^[0-9]+$ ]] || die "expected count after $a (e.g. $a 62; use 0 for none)"
      kind="$(bus_kind_from_flag "$a")"
      if [[ -n "$layout" ]]; then
        layout+=","
      fi
      layout+="${kind}:${count}"
      layout_total=$((layout_total + count))
      shift 2
      continue
    fi
    case "$a" in
      --master-enabled)
        [[ -n "${2:-}" ]] || die "expected 0 or 1 after --master-enabled"
        export MASTER_ENABLED="$2"
        shift 2
        continue
        ;;
      --master-bus)
        [[ -n "${2:-}" && "${3:-}" =~ ^[0-9]+$ ]] || die "expected --master-bus <bus-flag> <count> (e.g. --master-bus --axi 1)"
        if ! is_bus_layout_flag "$2"; then
          die "unknown master bus flag: $2"
        fi
        export MASTER_BUS_LAYOUT="$(bus_kind_from_flag "$2"):${3}"
        shift 3
        continue
        ;;
      --*)
        die "unknown gen flag: $a (see amba_bus_registry.py / ./example.sh help)"
        ;;
      *)
        if [[ "$a" =~ ^[0-9]+$ ]]; then
          if [[ -n "$positional" ]]; then
            die "ambiguous gen args: multiple positional counts ($positional, $a)"
          fi
          positional="$a"
        else
          die "unexpected gen argument: $a"
        fi
        shift
        ;;
    esac
  done

  if [[ -n "$layout" ]]; then
    if (( layout_total < 0 || layout_total > 256 )); then
      die "bus layout total out of range: $layout_total (allowed 0..256)"
    fi
    export BUS_LAYOUT="$layout"
    export NUM_SCPU="$layout_total"
    echo "[example.sh] BUS_LAYOUT=${BUS_LAYOUT} → CAMPAIGN_NUM_SCPU=${NUM_SCPU}"
    if (( layout_total == 0 )); then
      echo "[example.sh] solo mode (0 slave SCPU) — master.enabled defaults to 1"
      if [[ -z "${MASTER_ENABLED:-}" ]]; then
        export MASTER_ENABLED=1
      fi
    fi
    if [[ -n "$positional" && "$positional" != "$layout_total" ]]; then
      die "positional count $positional disagrees with bus layout total $layout_total"
    fi
    return 0
  fi

  unset BUS_LAYOUT || true
  if [[ -n "$positional" ]]; then
    parse_num_scpu "$positional"
  elif [[ -n "${NUM_SCPU:-}" ]]; then
    parse_num_scpu "${NUM_SCPU}"
  fi
}

run_gen() {
  # No layout args → yaml default (3 active slaves), not a stale solo stamp
  if [[ -z "${NUM_SCPU:-}" && -z "${BUS_LAYOUT:-}" ]]; then
    export NUM_SCPU=3
    echo "[example.sh] default CAMPAIGN_NUM_SCPU=3 (yaml active slaves)"
  fi
  local slots="${NUM_SCPU:-$(grep -E '^[[:space:]]*`define[[:space:]]+CAMPAIGN_NUM_SCPU[[:space:]]+' "${ROOT}/include/campaign_params.vh" 2>/dev/null | awk '{print $3}' || echo default)}"
  step "[1/2] Generate campaign firmware + Verilog headers (NUM_SCPU=${slots})"
  [[ -d "$FW" ]] || die "firmware dir not found: $FW"
  ensure_py_deps

  cd "$FW"
  echo "[gen] config    → CAMPAIGN_NUM_SCPU=${slots} → manifest, cpus.mk, campaign_scale.vh"
  local -a cfg_args=(make config)
  [[ -n "${NUM_SCPU:-}" ]] && cfg_args+=(NUM_SCPU="${NUM_SCPU}")
  [[ -n "${BUS_LAYOUT:-}" ]] && cfg_args+=(BUS_LAYOUT="${BUS_LAYOUT}")
  [[ -n "${MASTER_BUS_LAYOUT:-}" ]] && cfg_args+=(MASTER_BUS_LAYOUT="${MASTER_BUS_LAYOUT}")
  [[ -n "${MASTER_ENABLED:-}" ]] && cfg_args+=(MASTER_ENABLED="${MASTER_ENABLED}")
  "${cfg_args[@]}"

  # Keep layout/solo env for nested `make config` deps (icodes, all, …)
  export NUM_SCPU BUS_LAYOUT MASTER_BUS_LAYOUT MASTER_ENABLED

  echo "[gen] soc_init  → soc_init_seq.vh, campaign_soc_platform.vh"
  make soc_init

  echo "[gen] manifest  → campaign_manifest.vh"
  make manifest

  echo "[gen] icodes    → icode_pool.bin, icode_map.vh, tb_full_campaign_gen.vh"
  make icodes

  if [[ -n "${BUS_LAYOUT:-}" || -n "${MASTER_BUS_LAYOUT:-}" ]]; then
    echo "[gen] bus_connect → verif_soc_bus_connect.vh (manifest bus ports)"
    make bus_connect
  fi

  echo "[gen] VCPU bins + merge → full_campaign_unified.hex"
  make all

  echo "[gen] filelists + sim scripts → eda/*/*.list, scripts/{iverilog,verilator,vcs,xcelium,verdi}/"
  cd "$ROOT"
  make filelists

  echo ""
  echo "[gen] Artifacts:"
  ls -la build/*.bin 2>/dev/null || true
  ls -la "${ROOT}/firmware/"*.hex 2>/dev/null || true
  ls -la "${ROOT}/include/tb_full_campaign_gen.vh" \
         "${ROOT}/include/icode_map.vh" \
         "${ROOT}/include/campaign_manifest.vh" 2>/dev/null || true
  ls -la "${ROOT}/filelists/"*.f 2>/dev/null | head -16 || true
  ls -la "${ROOT}/scripts/verdi/"*.sh 2>/dev/null | head -8 || true
}

run_verdi() {
  local view="${1:-full_campaign}"
  local script="${ROOT}/scripts/verdi/${view}.sh"
  step "Verdi — view=${view} (source + VCD if sim already ran)"
  [[ -x "$script" ]] || die "missing $script — run: ./example.sh gen"
  shift || true
  exec "$script" "$@"
}

run_soc_manifest() {
  step "iverilog soc-manifest (integration TB — real AMBA bridges)"
  need_cmd iverilog
  need_cmd vvp

  cd "$ROOT"
  make soc-manifest
}

run_chip_top() {
  step "iverilog chip-top-example (soc_hierarchy yaml compile smoke)"
  need_cmd iverilog
  need_cmd vvp

  cd "$ROOT"
  make chip-top-example
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
  (none)|all [N]   Generate firmware + run full_campaign (+ optional N slave SCPU)
  gen [N]          Generation only; N = slave SCPU count (SCPU1..N), 0 = solo MVCPU
  gen --axi 0      Solo: 0 slave bus slots; SCPU0 master superset (enabled by default)
  gen --master-enabled 0|1   Force SCPU0 FW/agent role on or off
  gen --master-bus --axi 1   Master-only bus port (S00_AXI), in addition to slave layout
  gen --axi A ...  Bus layout: flag order = slot order from SCPU1 (low cpu_id first)
                   Legacy: --axi/--ahb/--apb → axi4lite/ahb_lite/apb3
                   All AMBA flags: --apb2..5 --axi3/4/5 --axistream --ace --chi --niu …
                   List: python3 -c "from amba_bus_registry import BUS_TYPES; print(sorted(BUS_TYPES))"
  sim              Simulation only (make full_campaign; rebuilds fw via Makefile)
  manifest         Integration TB (make soc-manifest — Phase A/B/C, 23 checks)
  chip-top         Chip top smoke (make chip-top-example — yaml hierarchy)
  vcd              Re-run verify_vcd.py on existing VCD files
  verdi [view]     Open Synopsys Verdi (default: full_campaign; needs gen + optional sim)
  clean            Remove gen/sim artifacts (fw build/hex/hdr, generated .vh, filelists, scripts)
  help             Show this message

Environment:
  NUM_SCPU     Same as gen N (alternative to positional argument)
  BUS_LAYOUT   Ordered bus segments (axi:62,ahb:1,apb:1) — set by gen --axi/--ahb/--apb/--task
  LOG_FULL     Per-CPU VCD log directory (default: .../VerifCPU/logs/full_campaign)

Examples:
  ./example.sh
  ./example.sh gen 64
  ./example.sh gen --axi 62 --ahb 1 --apb 1
  ./example.sh gen --apb 1 --axi 62 --ahb 1   # APB at SCPU1, then AXI, then AHB
  ./example.sh all 64
  ./example.sh gen && ./example.sh sim
  ./example.sh verdi                    # RTL + tb_full_campaign.vcd
  ./example.sh verdi soc_manifest_scale
  NUM_SCPU=40 ./example.sh gen
  LOG_FULL=/tmp/vcd ./example.sh sim
EOF
}

main() {
  local cmd="${1:-all}"
  shift || true

  case "$cmd" in
    all|full|verify|gen|generate)
      parse_gen_args "$@"
      ;;
  esac

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
    manifest|soc-manifest)
      run_soc_manifest
      ;;
    chip-top|chip-top-example)
      run_chip_top
      ;;
    vcd|check-vcd)
      run_vcd_only
      ;;
    verdi|verdi-gui|gui)
      shift || true
      run_verdi "$@"
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