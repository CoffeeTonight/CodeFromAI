#!/usr/bin/env python3
"""Generate simulation/integration filelists for verif_cpu_verilog.

Mirrors Makefile RTL groupings (FULL_RTL, BUS_RTL, MANIFEST_RTL, …).
Paths are relative to verif_cpu_verilog/ (iverilog / vcs / xcelium cwd).

Usage:
  python3 tools/gen_filelist.py
  make filelists
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "filelists"
EDA_DIR = OUT_DIR / "eda"
VERDI_DIR = ROOT / "scripts" / "verdi"
VCS_DIR = ROOT / "scripts" / "vcs"
XCELIUM_DIR = ROOT / "scripts" / "xcelium"
IVERILOG_DIR = ROOT / "scripts" / "iverilog"
VERILATOR_DIR = ROOT / "scripts" / "verilator"
SIM_LIB = ROOT / "scripts" / "lib"
SCRIPTS_DIR = ROOT / "scripts"

# Keep in sync with Makefile RTL / BUS_RTL / FULL_RTL / …
VCPU_RTL = [
    "rtl/verif_cpu_bus.v",
    "rtl/verif_cpu_unified_pool.v",
    "rtl/verif_cpu_txn_recorder.v",
    "rtl/verif_cpu_core.v",
]
RTL_CORE = VCPU_RTL  # alias (Makefile: RTL)

SOC_RTL = [
    "rtl/simple_soc.v",
    "rtl/verif_orchestrator.v",
    "rtl/verif_agent.v",
]

FULL_RTL = RTL_CORE + [
    "rtl/verif_soc_bus.v",
    *SOC_RTL,
]

BUS_RTL = [
    "rtl/verif_apb2_master.v",
    "rtl/verif_apb_master.v",
    "rtl/verif_apb4_master.v",
    "rtl/verif_apb5_master.v",
    "rtl/verif_ahb_lite_master.v",
    "rtl/verif_ahb5_lite_master.v",
    "rtl/verif_ahb_master.v",
    "rtl/verif_axi_lite_master.v",
    "rtl/verif_axi_full_master.v",
    "rtl/verif_apb2_slave_simple.v",
    "rtl/verif_apb_slave_simple.v",
    "rtl/verif_ahb_lite_slave_simple.v",
    "rtl/verif_axi_full_slave_simple.v",
]

STUB_BUS_RTL = [
    "rtl/verif_axistream_master.v",
    "rtl/verif_ace_master.v",
    "rtl/verif_ace_lite_master.v",
    "rtl/verif_chi_master.v",
    "rtl/verif_niu_master.v",
]

MANIFEST_RTL = RTL_CORE + [
    "rtl/verif_orchestrator.v",
    "rtl/verif_agent.v",
]

CHIP_TOP_RTL = MANIFEST_RTL

SOC_CELL_RTL = ["rtl/verif_vcpu_soc_cell.v"]

INCDIRS = [
    "+incdir+include",
    "+incdir+firmware/campaign/include",
]

GEN_HEADERS_COMMON = [
    "include/campaign_params.vh",
    "include/campaign_scale.vh",
    "include/campaign_manifest.vh",
    "include/icode_map.vh",
    "include/icode_bind.vh",
    "include/campaign_soc_platform.vh",
    "include/soc_init_seq.vh",
    "include/verif_soc_bus_connect.vh",
]

GEN_HEADERS_CAMPAIGN = GEN_HEADERS_COMMON + [
    "include/tb_full_campaign_gen.vh",
]

GEN_HEADERS_MANIFEST = GEN_HEADERS_COMMON + [
    "include/tb_soc_manifest_defs.vh",
    "include/tb_soc_manifest_gen.vh",
    "include/tb_soc_manifest_decode.vh",
    "include/verif_manifest_soc_bus_read.vh",
    "include/verif_manifest_soc_bus_write.vh",
]

GEN_HEADERS_MANIFEST_SCALE = GEN_HEADERS_MANIFEST + [
    "include/tb_soc_manifest_scale_defs.vh",
    "include/tb_soc_manifest_scale_gen.vh",
    "include/verif_manifest_scale_soc_bus_read.vh",
    "include/verif_manifest_scale_soc_bus_write.vh",
]

GEN_HEADERS_CHIP_TOP = GEN_HEADERS_COMMON + [
    "include/chip_top_example_gen.vh",
    "include/chip_top_decode.vh",
    "include/verif_chip_soc_bus_read.vh",
    "include/verif_chip_soc_bus_write.vh",
]

FW_ARTIFACTS = [
    "firmware/full_campaign_unified.hex",
    "firmware/full_campaign_vcpu.hex",
    "firmware/campaign/build/icode_pool.bin",
    "firmware/campaign/build/full_campaign_vcpu.bin",
]

RTL_ALL = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "rtl").glob("*.v"))

# EDA GUI views (Verdi / SimVision / Xcelium -import). Combined flist = one -f import.
VERDI_VIEWS: list[dict] = [
    {
        "id": "full_campaign",
        "title": "Authoritative campaign TB",
        "flist": "full_campaign.f",
        "top": "tb_full_campaign",
        "defines": [],
        "vcd": "sim_build/tb_full_campaign.vcd",
        "extra_vcd": [
            "logs/full_campaign/SCPU1.vcd",
            "logs/full_campaign/SCPU2.vcd",
            "logs/full_campaign/SCPU3.vcd",
        ],
    },
    {
        "id": "soc_manifest",
        "title": "Integration TB — manifest slaves",
        "flist": "soc_manifest.f",
        "top": "tb_soc_manifest",
        "defines": ["+define+VERIF_MANIFEST_SOC_TB"],
        "vcd": "sim_build/tb_soc_manifest.vcd",
        "extra_vcd": [],
    },
    {
        "id": "soc_manifest_scale",
        "title": "Scale integration TB — BUS_LAYOUT flat g_slv[]",
        "flist": "soc_manifest_scale.f",
        "top": "tb_soc_manifest_scale",
        "defines": ["+define+VERIF_MANIFEST_SCALE_TB"],
        "vcd": "sim_build/tb_soc_manifest_scale.vcd",
        "extra_vcd": [],
    },
    {
        "id": "chip_top_example",
        "title": "Chip top smoke — soc_hierarchy yaml",
        "flist": "chip_top_example.f",
        "top": "chip_top_example",
        "defines": ["+define+VERIF_CHIP_SOC_TB"],
        "vcd": "sim_build/chip_top_example.vcd",
        "extra_vcd": [],
    },
    {
        "id": "integration_dut",
        "title": "Customer integration — RTL only (no TB)",
        "flist": "integration_dut.f",
        "top": "verif_vcpu_soc_cell",
        "defines": [],
        "vcd": None,
        "extra_vcd": [],
    },
    {
        "id": "rtl_library",
        "title": "All RTL modules (browse library)",
        "flist": "rtl_all.f",
        "top": "verif_cpu_core",
        "defines": [],
        "vcd": None,
        "extra_vcd": [],
    },
]

# VCS / Xcelium (xrun) — per-view split: vcpu.list + rtl.list + tb_top.list
EDA_VIEWS: list[dict] = [
    {
        "id": "full_campaign",
        "title": "Authoritative campaign TB",
        "top": "tb_full_campaign",
        "tb": "tb/tb_full_campaign.v",
        "rtl": ["rtl/verif_soc_bus.v", *SOC_RTL],
        "defines": [],
        "headers": GEN_HEADERS_CAMPAIGN,
    },
    {
        "id": "soc_manifest",
        "title": "Integration TB — manifest slaves",
        "top": "tb_soc_manifest",
        "tb": "tb/tb_soc_manifest.v",
        "rtl": ["rtl/verif_orchestrator.v", "rtl/verif_agent.v", *BUS_RTL, *SOC_CELL_RTL],
        "defines": ["+define+VERIF_MANIFEST_SOC_TB"],
        "headers": GEN_HEADERS_MANIFEST,
    },
    {
        "id": "soc_manifest_scale",
        "title": "Scale integration TB",
        "top": "tb_soc_manifest_scale",
        "tb": "tb/tb_soc_manifest_scale.v",
        "rtl": ["rtl/verif_orchestrator.v", "rtl/verif_agent.v", *BUS_RTL, *SOC_CELL_RTL],
        "defines": ["+define+VERIF_MANIFEST_SCALE_TB"],
        "headers": GEN_HEADERS_MANIFEST_SCALE,
    },
    {
        "id": "chip_top_example",
        "title": "Chip top smoke",
        "top": "chip_top_example",
        "tb": "tb/chip_top_example.v",
        "rtl": [
            "rtl/verif_orchestrator.v",
            "rtl/verif_agent.v",
            *BUS_RTL,
            *STUB_BUS_RTL,
            *SOC_CELL_RTL,
        ],
        "defines": ["+define+VERIF_CHIP_SOC_TB"],
        "headers": GEN_HEADERS_CHIP_TOP,
    },
    {
        "id": "integration_dut",
        "title": "Customer chip integration (RTL only)",
        "top": "verif_vcpu_soc_cell",
        "tb": None,
        "rtl": ["rtl/verif_orchestrator.v", "rtl/verif_agent.v", *BUS_RTL, *SOC_CELL_RTL],
        "defines": [],
        "headers": [
            "include/verif_soc_bus_connect.vh",
            "include/verif_amba_connect_macros.vh",
        ],
    },
]

_VERDI_VCD: dict[str, str | None] = {v["id"]: v.get("vcd") for v in VERDI_VIEWS}


def _banner(title: str, note: str) -> list[str]:
    return [
        f"// {title}",
        f"// {note}",
        "// Generated by tools/gen_filelist.py — do not edit",
        "// Paths relative to verif_cpu_verilog/ (package root)",
        "",
    ]


def _emit_incdirs() -> list[str]:
    return [*_banner("VerifCPU include search paths", "Include with -f incdirs.f"), *INCDIRS, ""]


def _emit_files(
    paths: list[str],
    *,
    title: str,
    note: str,
    tb: str | None = None,
    defines: list[str] | None = None,
    headers: list[str] | None = None,
    extras: list[str] | None = None,
) -> str:
    lines = _banner(title, note)
    if defines:
        lines.extend(defines)
        lines.append("")
    lines.extend(paths)
    if tb:
        lines.append(tb)
    lines.append("")
    if headers:
        lines.append("// --- generated headers (iverilog: -I include; compile deps) ---")
        for h in headers:
            lines.append(f"// {h}")
        lines.append("")
    if extras:
        lines.extend(extras)
    return "\n".join(lines) + "\n"


def _emit_verdi_combined(source_flist: str, *, top: str) -> str:
    """Single filelist for Verdi GUI: Import Design → Add one .f."""
    src = (OUT_DIR / source_flist).read_text(encoding="utf-8")
    lines: list[str] = [
        f"// Verdi / SimVision combined import — mirrors filelists/{source_flist}",
        f"// Top: {top}",
        "// Generated by tools/gen_filelist.py — do not edit",
        "// Usage (package root):  verdi -sv -f filelists/verdi_<view>.f -top <top>",
        "",
        *INCDIRS,
        "",
    ]
    for raw in src.splitlines():
        if raw.startswith("// iverilog example:"):
            continue
        if raw.startswith("// Paths relative to"):
            continue
        if raw.startswith("// Generated by tools/gen_filelist"):
            continue
        lines.append(raw)
    return "\n".join(lines).rstrip() + "\n"


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def _emit_verdi_launcher(view: dict) -> str:
    vid = view["id"]
    top = view["top"]
    vcd = view.get("vcd")
    extra = view.get("extra_vcd") or []
    combined = f"filelists/verdi_{vid}.f"
    lines = [
        "#!/usr/bin/env bash",
        f"# Open {view['title']} in Synopsys Verdi (source + optional VCD).",
        "# Requires: ./example.sh gen  (generated .vh + filelists)",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        'VERDI="${VERDI:-verdi}"',
        f'TOP="${{VERDI_TOP:-{top}}}"',
        f'FLIST="{combined}"',
        'WAVE="${1:-}"',
        "",
        'if ! command -v "$VERDI" >/dev/null 2>&1; then',
        '  echo "[verdi] $VERDI not in PATH — set VERDI= or load Synopsys env (module load vcs)" >&2',
        "  exit 1",
        "fi",
        '[[ -f "$FLIST" ]] || { echo "[verdi] missing $FLIST — run: ./example.sh gen" >&2; exit 1; }',
        "",
        "ARGS=(-sv -nologo -f \"$FLIST\" -top \"$TOP\")",
    ]
    if vcd:
        lines.extend([
            f'DEFAULT_VCD="{vcd}"',
            'if [[ -z "$WAVE" && -f "$DEFAULT_VCD" ]]; then',
            '  WAVE="$DEFAULT_VCD"',
            "fi",
        ])
    lines.extend([
        'if [[ -n "$WAVE" ]]; then',
        '  if [[ -f "$WAVE" ]]; then',
        '    ARGS+=(-ssf "$WAVE")',
        '    echo "[verdi] waveform: $WAVE"',
        "  else",
        '    echo "[verdi] WARN waveform not found: $WAVE (source-only)" >&2',
        "  fi",
        "fi",
    ])
    for ev in extra:
        lines.append(f'# Optional per-CPU VCD: {ev}')
    lines.extend([
        'echo "[verdi] $VERDI -top $TOP -f $FLIST ${ARGS[*]:3}"',
        'exec "$VERDI" "${ARGS[@]}"',
        "",
    ])
    return "\n".join(lines)


def _emit_vcs_compile() -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# VCS compile (-kdb) for Verdi hierarchy. Usage: ./scripts/vcs/compile.sh <view>",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        'VCS="${VCS:-vcs}"',
        'VIEW="${1:-full_campaign}"',
        "",
        'if ! command -v "$VCS" >/dev/null 2>&1; then',
        '  echo "[vcs] $VCS not in PATH" >&2; exit 1',
        "fi",
        "",
        "case \"$VIEW\" in",
    ]
    for view in VERDI_VIEWS:
        lines.append(
            f'  {view["id"]}) TOP="${{VERDI_TOP:-{view["top"]}}}"; '
            f'FLIST="filelists/verdi_{view["id"]}.f" ;;'
        )
    lines.extend([
        "  *)",
        '    echo "[vcs] unknown view: $VIEW" >&2',
        f'    echo "  views: {" ".join(v["id"] for v in VERDI_VIEWS)}" >&2',
        "    exit 1 ;;",
        "esac",
        "",
        'OUTDIR="sim_build/vcs_${VIEW}"',
        '[[ -f "$FLIST" ]] || { echo "[vcs] missing $FLIST — run: ./example.sh gen" >&2; exit 1; }',
        "",
        'mkdir -p "$OUTDIR"',
        'echo "[vcs] compile view=$VIEW top=$TOP → $OUTDIR/simv"',
        '"$VCS" -sverilog -full64 -kdb -debug_access+all \\',
        '  -f "$FLIST" -top "$TOP" -o "$OUTDIR/simv" -Mdir="$OUTDIR/csrc"',
        'echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir [-ssf <wave.fsdb>]"',
        "",
    ])
    return "\n".join(lines)


def _emit_list_file(
    paths: list[str],
    *,
    title: str,
    note: str,
    extras: list[str] | None = None,
) -> str:
    lines = [
        f"# {title}",
        f"# {note}",
        "# Generated by tools/gen_filelist.py — do not edit",
        "# Paths relative to verif_cpu_verilog/ (package root)",
        "",
    ]
    lines.extend(paths)
    if extras:
        lines.append("")
        lines.extend(extras)
    lines.append("")
    return "\n".join(lines)


def _emit_eda_view(view: dict, *, optional: set[str]) -> list[tuple[str, str]]:
    vid = view["id"]
    out = EDA_DIR / vid
    out.mkdir(parents=True, exist_ok=True)
    specs: list[tuple[str, str]] = []

    vcpu = _check_paths(VCPU_RTL, optional)
    rtl = _check_paths(view["rtl"], optional)
    tb = view.get("tb")
    defines = view.get("defines") or []
    headers = view.get("headers") or []
    top = view["top"]

    files: list[tuple[str, str, list[str], str | None]] = [
        (
            "incdirs.list",
            "Include search paths (+incdir+)",
            INCDIRS,
            "VCS / xrun: -f incdirs.list (first)",
        ),
        (
            "vcpu.list",
            "VCPU RTL — verif_cpu_core + bus/pool/recorder",
            vcpu,
            "Shared VCPU block; same across views",
        ),
        (
            "rtl.list",
            f"Platform RTL — {view['title']}",
            rtl,
            "SoC / orchestrator / AMBA bridges / generated cells (no VCPU core)",
        ),
    ]
    if tb:
        files.append((
            "tb_top.list",
            f"Testbench top — {top}",
            [tb],
            f"Compile last; xrun/vcs -top {top}",
        ))
    else:
        (out / "tb_top.list").write_text(
            _emit_list_file(
                [],
                title=f"No TB — integration DUT top={top}",
                note="Empty; set -top to your chip or use rtl.list + vcpu.list only",
                extras=[f"# TOP={top}"],
            ),
            encoding="utf-8",
        )
        specs.append((f"eda/{vid}/tb_top.list", "empty (integration DUT)"))

    for name, title, paths, note in files:
        (out / name).write_text(
            _emit_list_file(paths, title=title, note=note),
            encoding="utf-8",
        )
        specs.append((f"eda/{vid}/{name}", title))

    (out / "defines.list").write_text(
        _emit_list_file(
            defines,
            title=f"Compile defines — {vid}",
            note="Optional; omit if your flow injects defines elsewhere",
            extras=[f"# TOP={top}"] + ([f"# {h}" for h in headers] if headers else []),
        ),
        encoding="utf-8",
    )
    specs.append((f"eda/{vid}/defines.list", "defines + header deps (comments)"))

    (out / "top.txt").write_text(f"{top}\n", encoding="utf-8")
    specs.append((f"eda/{vid}/top.txt", f"top module: {top}"))

    vcd = _VERDI_VCD.get(vid)
    if vcd:
        (out / "vcd.txt").write_text(f"{vcd}\n", encoding="utf-8")
        specs.append((f"eda/{vid}/vcd.txt", "expected VCD path (after sim)"))

    # Master manifest — paths from package root (cwd = verif_cpu_verilog/)
    eda_prefix = f"filelists/eda/{vid}"
    manifest = [
        f"# EDA compile manifest — {view['title']}",
        "# Order: incdirs → defines → vcpu → rtl → tb_top",
        f"# VCS:  vcs -sverilog -full64 -F {eda_prefix}/manifest.list -top {top}",
        f"# xrun: xrun -64bit -sv -F {eda_prefix}/manifest.list -top {top}",
        "# Run from verif_cpu_verilog/ (package root)",
        "",
        f"-F {eda_prefix}/incdirs.list",
        f"-F {eda_prefix}/defines.list",
        f"-F {eda_prefix}/vcpu.list",
        f"-F {eda_prefix}/rtl.list",
    ]
    if tb:
        manifest.append(f"-F {eda_prefix}/tb_top.list")
    (out / "manifest.list").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    specs.append((f"eda/{vid}/manifest.list", "ordered -F bundle"))

    return specs


def _eda_view_ids() -> str:
    return " ".join(v["id"] for v in EDA_VIEWS)


def _emit_eda_lib_sh() -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Shared helpers for generated simulator run scripts.",
        "# Generated by tools/gen_filelist.py — do not edit.",
        "",
        f'EDA_VIEWS="{_eda_view_ids()}"',
        "",
        "eda_require_view() {",
        '  local view="$1"',
        '  local m="filelists/eda/${view}/manifest.list"',
        '  if [[ ! -f "$m" ]]; then',
        '    echo "[eda] missing $m — run: ./example.sh gen" >&2',
        '    echo "[eda] views: $EDA_VIEWS" >&2',
        "    return 1",
        "  fi",
        "}",
        "",
        "eda_prefix() {",
        '  echo "filelists/eda/$1"',
        "}",
        "",
        "eda_top() {",
        '  cat "$(eda_prefix "$1")/top.txt"',
        "}",
        "",
        "eda_vcd() {",
        '  local f',
        '  f="$(eda_prefix "$1")/vcd.txt"',
        '  if [[ -f "$f" ]]; then cat "$f"; fi',
        "}",
        "",
        "eda_has_tb() {",
        '  local f="$(eda_prefix "$1")/tb_top.list"',
        '  grep -qvE "^#|^$" "$f" 2>/dev/null',
        "}",
        "",
        "# Emit -f flags for iverilog / tools that accept file lists directly.",
        "eda_iverilog_f_flags() {",
        '  local view="$1" p',
        '  p="$(eda_prefix "$view")"',
        '  for f in incdirs.list defines.list vcpu.list rtl.list tb_top.list; do',
        '    [[ -f "$p/$f" ]] || continue',
        '    grep -qvE "^#|^$" "$p/$f" 2>/dev/null || continue',
        '    printf -- "-f %s/%s " "$p" "$f"',
        "  done",
        "}",
        "",
        "# Source .v paths (one per line) from vcpu + rtl + tb_top lists.",
        "eda_source_files() {",
        '  local view="$1" p f line',
        '  p="$(eda_prefix "$view")"',
        '  for f in vcpu.list rtl.list tb_top.list; do',
        '    [[ -f "$p/$f" ]] || continue',
        '    while IFS= read -r line; do',
        '      [[ "$line" =~ ^# ]] && continue',
        '      [[ -z "$line" ]] && continue',
        '      [[ "$line" == +* ]] && continue',
        '      printf "%s\\n" "$line"',
        '    done < "$p/$f"',
        "  done",
        "}",
        "",
        "# +incdir+ → -I for Verilator.",
        "eda_verilator_incdirs() {",
        '  local view="$1" p line',
        '  p="$(eda_prefix "$view")/incdirs.list"',
        '  [[ -f "$p" ]] || return 0',
        '  while IFS= read -r line; do',
        '    [[ "$line" =~ ^\\+incdir\\+ ]] || continue',
        '    printf -- "-I%s " "${line#+incdir+}"',
        '  done < "$p"',
        "}",
        "",
        "# +define+NAME → -DNAME for Verilator.",
        "eda_verilator_defines() {",
        '  local view="$1" p line name',
        '  p="$(eda_prefix "$view")/defines.list"',
        '  [[ -f "$p" ]] || return 0',
        '  while IFS= read -r line; do',
        '    [[ "$line" =~ ^\\+define\\+ ]] || continue',
        '    name="${line#+define+}"',
        '    printf -- "-D%s " "$name"',
        '  done < "$p"',
        "}",
        "",
    ]) + "\n"


def _emit_view_wrapper(view_id: str) -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        f'exec "$(cd "$(dirname "$0")" && pwd)/run.sh" {view_id} "$@"',
        "",
    ])


def _emit_iverilog_run() -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Icarus Verilog — compile + run using filelists/eda/<view>/*.list",
        "# Usage: ./scripts/iverilog/run.sh [view]",
        "# Example: ./scripts/iverilog/run.sh full_campaign",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        "# shellcheck source=scripts/lib/eda_lists.sh",
        'source "$ROOT/scripts/lib/eda_lists.sh"',
        "",
        'VIEW="${1:-full_campaign}"',
        'IVERILOG="${IVERILOG:-iverilog}"',
        'VVP="${VVP:-vvp}"',
        "",
        'eda_require_view "$VIEW"',
        'TOP="${IVERILOG_TOP:-$(eda_top "$VIEW")}"',
        'OUTDIR="sim_build/iverilog_${VIEW}"',
        'VVP_OUT="$OUTDIR/sim.vvp"',
        'mkdir -p "$OUTDIR"',
        "",
        'if ! eda_has_tb "$VIEW"; then',
        '  echo "[iverilog] view=$VIEW has no TB — use integration flow or pick another view" >&2',
        "  exit 1",
        "fi",
        "",
        'if ! command -v "$IVERILOG" >/dev/null 2>&1; then',
        '  echo "[iverilog] $IVERILOG not in PATH" >&2; exit 1',
        "fi",
        'if ! command -v "$VVP" >/dev/null 2>&1; then',
        '  echo "[iverilog] $VVP not in PATH" >&2; exit 1',
        "fi",
        "",
        'VCD="$(eda_vcd "$VIEW")"',
        'if [[ -n "$VCD" ]]; then mkdir -p "$(dirname "$VCD")"; fi',
        "",
        'echo "[iverilog] view=$VIEW top=$TOP → $VVP_OUT"',
        'eval "$IVERILOG" -g2012 $(eda_iverilog_f_flags "$VIEW") -s "$TOP" -o "$VVP_OUT"',
        'echo "[iverilog] vvp $VVP_OUT"',
        '"$VVP" "$VVP_OUT"',
        'if [[ -n "$VCD" && -f "$VCD" ]]; then',
        '  echo "[iverilog] VCD: $VCD"',
        "fi",
        "",
    ])


def _emit_verilator_run() -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Verilator — compile + run (example flow; authoritative gate is iverilog).",
        "# Usage: ./scripts/verilator/run.sh [view]",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        "# shellcheck source=scripts/lib/eda_lists.sh",
        'source "$ROOT/scripts/lib/eda_lists.sh"',
        "",
        'VIEW="${1:-full_campaign}"',
        'VERILATOR="${VERILATOR:-verilator}"',
        "",
        'eda_require_view "$VIEW"',
        'TOP="${VERILATOR_TOP:-$(eda_top "$VIEW")}"',
        'OUTDIR="sim_build/verilator_${VIEW}"',
        'mkdir -p "$OUTDIR"',
        "",
        'if ! command -v "$VERILATOR" >/dev/null 2>&1; then',
        '  echo "[verilator] $VERILATOR not in PATH" >&2; exit 1',
        "fi",
        "",
        "mapfile -t SOURCES < <(eda_source_files \"$VIEW\")",
        'if [[ ${#SOURCES[@]} -eq 0 ]]; then',
        '  echo "[verilator] no sources for view=$VIEW" >&2; exit 1',
        "fi",
        "",
        'TRACE_ARGS=()',
        'if [[ "${VERILATOR_TRACE:-1}" == "1" ]]; then',
        '  TRACE_ARGS=(--trace-vcd)',
        "fi",
        "",
        'echo "[verilator] view=$VIEW top=$TOP sources=${#SOURCES[@]} → $OUTDIR"',
        'eval "$VERILATOR" --binary -j 0 --timing \\',
        "  $(eda_verilator_incdirs \"$VIEW\") \\",
        "  $(eda_verilator_defines \"$VIEW\") \\",
        '  --top-module "$TOP" \\',
        '  -Wno-fatal -Wno-WIDTH -Wno-UNOPTFLAT -Wno-STMTDLY -Wno-DECLFILENAME \\',
        '  -Mdir "$OUTDIR" "${TRACE_ARGS[@]}" "${SOURCES[@]}"',
        "",
        'EXE="$OUTDIR/V$TOP"',
        'if [[ ! -x "$EXE" ]]; then',
        '  echo "[verilator] missing executable $EXE" >&2; exit 1',
        "fi",
        'echo "[verilator] run $EXE"',
        '"$EXE"',
        'if [[ "${VERILATOR_TRACE:-1}" == "1" ]]; then',
        '  echo "[verilator] VCD trace under $OUTDIR/ (verilator --trace-vcd)"',
        "fi",
        "",
    ])


def _emit_vcs_run() -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Synopsys VCS — compile (if needed) + run simv.",
        "# Usage: ./scripts/vcs/run.sh [view]",
        "# Env: FORCE_COMPILE=1  VCS_VCD=<path>  VCS_SIMV_OPTS=\"+ntb_random_seed=1\"",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        "# shellcheck source=scripts/lib/eda_lists.sh",
        'source "$ROOT/scripts/lib/eda_lists.sh"',
        "",
        'VIEW="${1:-full_campaign}"',
        'eda_require_view "$VIEW"',
        'OUTDIR="sim_build/vcs_${VIEW}"',
        'SIMV="$OUTDIR/simv"',
        "",
        'if [[ ! -x "$SIMV" || "${FORCE_COMPILE:-0}" == "1" ]]; then',
        '  echo "[vcs] compile view=$VIEW"',
        '  "$ROOT/scripts/vcs/compile.sh" "$VIEW"',
        "fi",
        "",
        'VCD="${VCS_VCD:-$OUTDIR/sim.vcd}"',
        'mkdir -p "$OUTDIR"',
        'echo "[vcs] run $SIMV +vcd+$VCD"',
        '"$SIMV" +vcd+:"$VCD" ${VCS_SIMV_OPTS:-} | tee "$OUTDIR/sim.log"',
        'echo "[vcs] log=$OUTDIR/sim.log vcd=$VCD"',
        'echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir -ssf $VCD"',
        "",
    ])


def _emit_xcelium_run() -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Cadence Xcelium xrun — elaborate + simulate (single invocation).",
        "# Usage: ./scripts/xcelium/run.sh [view]",
        "# Env: XRUN_OPTS=\"-svseed random\"  XRUN_PROBE=1",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        "# shellcheck source=scripts/lib/eda_lists.sh",
        'source "$ROOT/scripts/lib/eda_lists.sh"',
        "",
        'VIEW="${1:-full_campaign}"',
        'XRUN="${XRUN:-xrun}"',
        "",
        'eda_require_view "$VIEW"',
        'TOP="${XRUN_TOP:-$(eda_top "$VIEW")}"',
        'MANIFEST="filelists/eda/${VIEW}/manifest.list"',
        'OUTDIR="sim_build/xcelium_${VIEW}"',
        'mkdir -p "$OUTDIR"',
        "",
        'if ! command -v "$XRUN" >/dev/null 2>&1; then',
        '  echo "[xrun] $XRUN not in PATH — load Cadence env" >&2; exit 1',
        "fi",
        "",
        'PROBE_TCL=""',
        'if [[ "${XRUN_PROBE:-1}" == "1" ]]; then',
        '  PROBE_TCL="-input @probe.tcl"',
        '  cat > "$OUTDIR/probe.tcl" <<EOF',
        "database -open waves -shm -default",
        "probe -create -all -depth all",
        "run",
        "exit",
        "EOF",
        "fi",
        "",
        'echo "[xrun] view=$VIEW top=$TOP → $OUTDIR/xcelium.d"',
        'eval "$XRUN" -64bit -sv -timescale 1ns/1ps \\',
        '  -F "$MANIFEST" -top "$TOP" \\',
        '  -access +rwc -status \\',
        '  -xmlibdirname "$OUTDIR/xcelium.d" \\',
        '  -clean ${PROBE_TCL} ${XRUN_OPTS:-}',
        'echo "[xrun] waves: ${OUTDIR}/xcelium.d/shm"',
        'echo "[xrun] SimVision: simvision -csdf ${OUTDIR}/xcelium.d"',
        "",
    ])


def _emit_sim_scripts_readme() -> str:
    lines = [
        "# Simulator run scripts — generated by tools/gen_filelist.py",
        "# Prerequisite: ./example.sh gen  (firmware + filelists/eda/<view>/*.list)",
        "# Run from verif_cpu_verilog/ (package root).",
        "#",
        f"# Views: {_eda_view_ids()}",
        "#",
        "# Per simulator:",
        "#   ./scripts/iverilog/run.sh [view]     — iverilog + vvp (authoritative)",
        "#   ./scripts/verilator/run.sh [view]    — Verilator --binary (example)",
        "#   ./scripts/vcs/run.sh [view]          — VCS compile + simv",
        "#   ./scripts/xcelium/run.sh [view]      — xrun elaborate + sim",
        "#",
        "# Per-view shortcuts (same as run.sh <view>):",
    ]
    for v in EDA_VIEWS:
        lines.append(f"#   ./scripts/iverilog/{v['id']}.sh")
    lines.extend([
        "#",
        "# Filelist layout: filelists/eda/<view>/{incdirs,vcpu,rtl,tb_top,defines}.list",
        "# Shared parser: scripts/lib/eda_lists.sh",
        "#",
        "# Examples:",
        "#   ./example.sh gen && ./scripts/iverilog/run.sh full_campaign",
        "#   ./scripts/vcs/run.sh soc_manifest_scale",
        "#   FORCE_COMPILE=1 ./scripts/vcs/run.sh chip_top_example",
        "#   VERILATOR_TRACE=0 ./scripts/verilator/run.sh full_campaign",
        "",
    ])
    return "\n".join(lines)


def _generate_sim_run_scripts() -> None:
    SIM_LIB.mkdir(parents=True, exist_ok=True)
    _write_executable(SIM_LIB / "eda_lists.sh", _emit_eda_lib_sh())

    sim_dirs = [
        (IVERILOG_DIR, _emit_iverilog_run),
        (VERILATOR_DIR, _emit_verilator_run),
        (VCS_DIR, _emit_vcs_run),
        (XCELIUM_DIR, _emit_xcelium_run),
    ]
    for sim_dir, emit_run in sim_dirs:
        sim_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(sim_dir / "run.sh", emit_run())
        for view in EDA_VIEWS:
            _write_executable(sim_dir / f"{view['id']}.sh", _emit_view_wrapper(view["id"]))

    (SCRIPTS_DIR / "README.txt").write_text(_emit_sim_scripts_readme(), encoding="utf-8")


def _emit_eda_readme() -> str:
    lines = [
        "# EDA filelists (VCS / Cadence Xcelium xrun)",
        "# Generated by tools/gen_filelist.py — run: ./example.sh gen",
        "#",
        "# Each view under eda/<view>/ has:",
        "#   incdirs.list   +incdir+ paths",
        "#   vcpu.list      VCPU core RTL (verif_cpu_*)",
        "#   rtl.list       SoC / bus / platform (view-specific)",
        "#   tb_top.list    testbench top .v",
        "#   defines.list   +define+ (optional)",
        "#   manifest.list  ordered -F bundle",
        "#   top.txt        top module name",
        "#",
        "# VCS example (package root):",
    ]
    for v in EDA_VIEWS:
        d = EDA_DIR / v["id"]
        lines.append(f"#   vcs -sverilog -full64 -F {d.relative_to(ROOT)}/manifest.list -top {v['top']}")
    lines.extend([
        "#",
        "# Xcelium / xrun example:",
    ])
    for v in EDA_VIEWS:
        d = EDA_DIR / v["id"]
        lines.append(
            f"#   xrun -64bit -sv -F {d.relative_to(ROOT)}/manifest.list -top {v['top']}"
        )
    lines.extend([
        "#",
        "# Or compose manually:",
        "#   vcs -f filelists/eda/full_campaign/incdirs.list \\",
        "#       -f filelists/eda/full_campaign/defines.list \\",
        "#       -f filelists/eda/full_campaign/vcpu.list \\",
        "#       -f filelists/eda/full_campaign/rtl.list \\",
        "#       -f filelists/eda/full_campaign/tb_top.list -top tb_full_campaign",
        "#",
        "# Helpers:",
        "#   ./scripts/vcs/compile.sh   ./scripts/vcs/run.sh",
        "#   ./scripts/xcelium/xrun.sh  ./scripts/xcelium/run.sh",
        "#   ./scripts/iverilog/run.sh  ./scripts/verilator/run.sh",
        "# See scripts/README.txt",
        "",
    ])
    return "\n".join(lines)


def _emit_vcs_compile_eda() -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# VCS compile using split EDA lists (vcpu / rtl / tb_top).",
        "# Usage: ./scripts/vcs/compile.sh <view>   OR   ./scripts/vcs/compile.sh eda <view>",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        'VCS="${VCS:-vcs}"',
        'MODE="${1:-full_campaign}"',
        'VIEW="${2:-}"',
        "",
        'if [[ "$MODE" == "eda" ]]; then',
        '  VIEW="${2:-full_campaign}"',
        "else",
        '  VIEW="$MODE"',
        "fi",
        "",
        'MANIFEST="filelists/eda/${VIEW}/manifest.list"',
        'TOPFILE="filelists/eda/${VIEW}/top.txt"',
        "",
        'if ! command -v "$VCS" >/dev/null 2>&1; then',
        '  echo "[vcs] $VCS not in PATH" >&2; exit 1',
        "fi",
        '[[ -f "$MANIFEST" ]] || {',
        '  echo "[vcs] missing $MANIFEST — run: ./example.sh gen" >&2',
        f'  echo "  views: {" ".join(v["id"] for v in EDA_VIEWS)}" >&2',
        "  exit 1",
        "}",
        'TOP="${VERDI_TOP:-$(cat "$TOPFILE")}"',
        'OUTDIR="sim_build/vcs_${VIEW}"',
        'mkdir -p "$OUTDIR"',
        "",
        'echo "[vcs] view=$VIEW top=$TOP lists=filelists/eda/$VIEW/{vcpu,rtl,tb_top}.list"',
        '"$VCS" -sverilog -full64 -kdb -debug_access+all \\',
        '  -F "$MANIFEST" -top "$TOP" \\',
        '  -o "$OUTDIR/simv" -Mdir="$OUTDIR/csrc"',
        'echo "[vcs] verdi -dbdir $OUTDIR/simv.daidir"',
        "",
    ]
    return "\n".join(lines)


def _emit_xcelium_xrun() -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# Cadence Xcelium xrun using split EDA lists.",
        "# Usage: ./scripts/xcelium/xrun.sh <view>",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")/../.." && pwd)"',
        'cd "$ROOT"',
        'XRUN="${XRUN:-xrun}"',
        'VIEW="${1:-full_campaign}"',
        "",
        'MANIFEST="filelists/eda/${VIEW}/manifest.list"',
        'TOPFILE="filelists/eda/${VIEW}/top.txt"',
        "",
        'if ! command -v "$XRUN" >/dev/null 2>&1; then',
        '  echo "[xrun] $XRUN not in PATH — load Cadence env" >&2; exit 1',
        "fi",
        '[[ -f "$MANIFEST" ]] || {',
        '  echo "[xrun] missing $MANIFEST — run: ./example.sh gen" >&2',
        f'  echo "  views: {" ".join(v["id"] for v in EDA_VIEWS)}" >&2',
        "  exit 1",
        "}",
        'TOP="${XRUN_TOP:-$(cat "$TOPFILE")}"',
        'OUTDIR="sim_build/xcelium_${VIEW}"',
        'mkdir -p "$OUTDIR"',
        "",
        'echo "[xrun] view=$VIEW top=$TOP lists=filelists/eda/$VIEW/{vcpu,rtl,tb_top}.list"',
        '"$XRUN" -64bit -sv -timescale 1ns/1ps \\',
        '  -F "$MANIFEST" -top "$TOP" \\',
        '  -elaborate -clean \\',
        '  -xmlibdirname "$OUTDIR/xcelium.d"',
        'echo "[xrun] sim: cd $OUTDIR && xrun -R  (or your probe flow)"',
        "",
    ]
    return "\n".join(lines)


def _emit_verdi_readme() -> str:
    lines = [
        "# Verdi / VCS helpers — generated by tools/gen_filelist.py",
        "# Run from verif_cpu_verilog/ after:  ./example.sh gen",
        "",
        "# Quick open (source browser + VCD if sim already ran):",
    ]
    for v in VERDI_VIEWS:
        lines.append(f"#   ./scripts/verdi/{v['id']}.sh")
    lines.extend([
        "",
        "# Manual Verdi (single combined filelist):",
    ])
    for v in VERDI_VIEWS:
        wave = f" -ssf {v['vcd']}" if v.get("vcd") else ""
        lines.append(
            f"#   verdi -sv -f filelists/verdi_{v['id']}.f -top {v['top']}{wave}"
        )
    lines.extend([
        "",
        "# VCS + KDB (full hierarchy, then Verdi -dbdir):",
        "#   ./scripts/vcs/compile.sh full_campaign",
        "#   verdi -dbdir sim_build/vcs_full_campaign/simv.daidir -ssf waves.fsdb",
        "",
        "# Environment:",
        "#   VERDI=verdi   VCS=vcs   VERDI_TOP=<override>",
        "",
    ])
    return "\n".join(lines)


def _check_paths(paths: list[str], optional: set[str] | None = None) -> list[str]:
    optional = optional or set()
    missing = [p for p in paths if p not in optional and not (ROOT / p).is_file()]
    if missing:
        print("[filelist] WARN missing (run ./example.sh gen first):", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
    return paths


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    opt = set(GEN_HEADERS_COMMON + GEN_HEADERS_CAMPAIGN + GEN_HEADERS_MANIFEST
              + GEN_HEADERS_MANIFEST_SCALE + GEN_HEADERS_CHIP_TOP + FW_ARTIFACTS
              + SOC_CELL_RTL)

    specs: list[tuple[str, str]] = []

    (OUT_DIR / "incdirs.f").write_text("\n".join(_emit_incdirs()), encoding="utf-8")
    specs.append(("incdirs.f", "include dirs"))

    groups = [
        ("rtl_core.f", "Core VCPU RTL (no SoC)", RTL_CORE, None, None, None),
        ("rtl_soc.f", "Campaign SoC model", SOC_RTL + ["rtl/verif_soc_bus.v"], None, None, None),
        ("rtl_bus.f", "AMBA bridge + simple slave models", BUS_RTL, None, None, None),
        ("rtl_bus_all.f", "AMBA bridges + manifest-only stubs", BUS_RTL + STUB_BUS_RTL, None, None, None),
        ("rtl_soc_cell.f", "Generated VCPU+bridge cells", SOC_CELL_RTL, None, None, None),
        ("rtl_all.f", "All RTL under rtl/ (EDA library browse)", RTL_ALL, None, None, None),
        (
            "full_campaign.f",
            "Authoritative campaign TB (./example.sh default)",
            _check_paths(FULL_RTL, opt),
            "tb/tb_full_campaign.v",
            None,
            GEN_HEADERS_CAMPAIGN,
        ),
        (
            "soc_manifest.f",
            "Integration TB — active slaves + real bridges",
            _check_paths(MANIFEST_RTL + BUS_RTL + SOC_CELL_RTL, opt),
            "tb/tb_soc_manifest.v",
            ["+define+VERIF_MANIFEST_SOC_TB"],
            GEN_HEADERS_MANIFEST,
        ),
        (
            "soc_manifest_scale.f",
            "Scale integration TB — BUS_LAYOUT flat g_slv[]",
            _check_paths(MANIFEST_RTL + BUS_RTL + SOC_CELL_RTL, opt),
            "tb/tb_soc_manifest_scale.v",
            ["+define+VERIF_MANIFEST_SCALE_TB"],
            GEN_HEADERS_MANIFEST_SCALE,
        ),
        (
            "chip_top_example.f",
            "Chip top smoke — soc_hierarchy yaml",
            _check_paths(CHIP_TOP_RTL + BUS_RTL + STUB_BUS_RTL + SOC_CELL_RTL, opt),
            "tb/chip_top_example.v",
            ["+define+VERIF_CHIP_SOC_TB"],
            GEN_HEADERS_CHIP_TOP,
        ),
        (
            "integration_dut.f",
            "Customer chip integration — RTL only (no TB, no simple_soc)",
            _check_paths(MANIFEST_RTL + BUS_RTL + SOC_CELL_RTL, opt),
            None,
            None,
            [
                "include/verif_soc_bus_connect.vh",
                "include/verif_amba_connect_macros.vh",
            ],
        ),
    ]

    for name, title, rtl, tb, defines, headers in groups:
        text = _emit_files(
            rtl,
            title=title,
            note=f"iverilog example: iverilog -g2012 -I include -f filelists/{name}",
            tb=tb,
            defines=defines,
            headers=headers,
        )
        (OUT_DIR / name).write_text(text, encoding="utf-8")
        specs.append((name, title))

    # Verdi combined imports (incdirs + defines + RTL inlined from sibling .f)
    for view in VERDI_VIEWS:
        src = view["flist"]
        if not (OUT_DIR / src).is_file():
            continue
        combined_name = f"verdi_{view['id']}.f"
        (OUT_DIR / combined_name).write_text(
            _emit_verdi_combined(src, top=view["top"]),
            encoding="utf-8",
        )
        specs.append((combined_name, f"Verdi import — {view['title']}"))

    # EDA split lists (VCS / Xcelium)
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    for view in EDA_VIEWS:
        specs.extend(_emit_eda_view(view, optional=opt))
    (EDA_DIR / "README.txt").write_text(_emit_eda_readme(), encoding="utf-8")

    # Launch scripts
    VERDI_DIR.mkdir(parents=True, exist_ok=True)
    VCS_DIR.mkdir(parents=True, exist_ok=True)
    XCELIUM_DIR.mkdir(parents=True, exist_ok=True)
    for view in VERDI_VIEWS:
        _write_executable(VERDI_DIR / f"{view['id']}.sh", _emit_verdi_launcher(view))
    _write_executable(VCS_DIR / "compile.sh", _emit_vcs_compile_eda())
    _write_executable(VCS_DIR / "compile_verdi.sh", _emit_vcs_compile())
    _write_executable(XCELIUM_DIR / "xrun.sh", _emit_xcelium_xrun())
    (VERDI_DIR / "README.txt").write_text(_emit_verdi_readme(), encoding="utf-8")
    _generate_sim_run_scripts()

    # Master index for human / scripting
    index_lines = [
        "# VerifCPU filelists — generated by tools/gen_filelist.py",
        "# Run from verif_cpu_verilog/:  iverilog -g2012 -f filelists/<name>.f",
        "",
    ]
    for name, title in specs:
        index_lines.append(f"#   {name:<28} {title}")
    index_lines.extend([
        "",
        "# iverilog:",
        "#   iverilog -g2012 -f filelists/incdirs.f -f filelists/full_campaign.f -o sim.vvp",
        "",
        "# Verdi (after ./example.sh gen; run sim first for VCD):",
        "#   ./scripts/verdi/full_campaign.sh",
        "#   verdi -sv -f filelists/verdi_full_campaign.f -top tb_full_campaign -ssf sim_build/tb_full_campaign.vcd",
        "",
        "# See scripts/verdi/README.txt for all views.",
        "",
        "# VCS / Xcelium (split lists per view):",
        "#   filelists/eda/full_campaign/{vcpu,rtl,tb_top}.list",
        "#   ./scripts/vcs/compile.sh full_campaign",
        "#   ./scripts/xcelium/xrun.sh full_campaign",
        "#   ./scripts/iverilog/run.sh full_campaign",
        "#   ./scripts/verilator/run.sh full_campaign",
        "# See filelists/eda/README.txt and scripts/README.txt",
        "",
    ])
    (OUT_DIR / "README.txt").write_text("\n".join(index_lines), encoding="utf-8")

    print(f"[filelist] Wrote {OUT_DIR}/ ({len(specs)} lists)")
    for name, _ in specs:
        print(f"  {OUT_DIR / name}")
    print(f"[filelist] EDA split lists → {EDA_DIR}/")
    for view in EDA_VIEWS:
        print(f"  {EDA_DIR / view['id']}/{{vcpu,rtl,tb_top}}.list")
    print(f"[filelist] Verdi launchers → {VERDI_DIR}/")
    for view in VERDI_VIEWS:
        print(f"  {VERDI_DIR / (view['id'] + '.sh')}")
    print("[filelist] Simulator run scripts → scripts/{iverilog,verilator,vcs,xcelium}/run.sh")
    print(f"  {SCRIPTS_DIR / 'README.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())