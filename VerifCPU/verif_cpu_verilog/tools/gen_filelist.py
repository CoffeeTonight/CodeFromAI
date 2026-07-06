#!/usr/bin/env python3
"""Generate simulation/integration filelists for verif_cpu_verilog.

Mirrors Makefile RTL groupings (FULL_RTL, BUS_RTL, MANIFEST_RTL, …).
Paths are relative to verif_cpu_verilog/ (iverilog / vcs / xcelium cwd).

Usage:
  python3 tools/gen_filelist.py
  make filelists
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "filelists"
WORK_DIR = OUT_DIR / "work"
TEST_DIR = OUT_DIR / "test"
EDA_DIR = OUT_DIR / "eda"
EDA_WORK_DIR = EDA_DIR / "work"
EDA_TEST_DIR = EDA_DIR / "test"
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
    "rtl/verif_cpu_sync.v",
    "rtl/verif_cpu_hw_force.v",
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

# --- Canonical 3-way split (prefer these over legacy per-view .f files) ---
# Matches Makefile MANIFEST_RTL / CHIP_TOP_RTL (no sync/hw_force — those are in SOC_RTL).
VCPU_STACK = RTL_CORE + [
    "rtl/verif_orchestrator.v",
    "rtl/verif_agent.v",
]

RTL_INTEGRATION = VCPU_STACK + BUS_RTL + ["rtl/verif_vcpu_soc_cell.v"]

# Authoritative full_campaign compile set (Makefile FULL_RTL).
TB_DUT_RTL = FULL_RTL

MANIFEST_RTL = VCPU_STACK
CHIP_TOP_RTL = VCPU_STACK
SOC_CELL_RTL = ["rtl/verif_vcpu_soc_cell.v"]

RTL_CONNECT_HEADERS = [
    "include/verif_soc_bus_connect.vh",
    "include/verif_amba_connect_macros.vh",
]

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
        "id": "rtl",
        "category": "work",
        "title": "Work — VerifCPU RTL for customer SoC (no TB)",
        "flist": "work/rtl.f",
        "top": "verif_vcpu_soc_cell",
        "defines": [],
        "vcd": None,
        "extra_vcd": [],
    },
    {
        "id": "full_campaign",
        "category": "test",
        "title": "Test — internal regression (simple_soc + full_campaign)",
        "flist": "test/tb_dut.f",
        "top": "tb_full_campaign",
        "defines": [],
        "vcd": "sim_build/tb_full_campaign.vcd",
        "extra_vcd": [],
    },
    {
        "id": "soc_manifest",
        "category": "test",
        "title": "Test — bridge wiring reference (tb_soc_manifest)",
        "flist": "test/soc_manifest.f",
        "top": "tb_soc_manifest",
        "defines": ["+define+VERIF_MANIFEST_SOC_TB"],
        "vcd": "sim_build/tb_soc_manifest.vcd",
        "extra_vcd": [],
    },
]

# VCS / Xcelium (xrun) — per-view split: vcpu.list + rtl.list + tb_top.list
EDA_WORK_VIEWS: list[dict] = [
    {
        "id": "integration",
        "category": "work",
        "title": "Work — customer SoC (RTL only, no TB)",
        "top": "verif_vcpu_soc_cell",
        "tb": None,
        "rtl": [*BUS_RTL, *SOC_CELL_RTL],
        "defines": [],
        "headers": RTL_CONNECT_HEADERS,
    },
]

EDA_TEST_VIEWS: list[dict] = [
    {
        "id": "full_campaign",
        "category": "test",
        "title": "Test — authoritative campaign TB",
        "top": "tb_full_campaign",
        "tb": "tb/tb_full_campaign.v",
        "rtl": ["rtl/verif_soc_bus.v", *SOC_RTL],
        "defines": [],
        "headers": GEN_HEADERS_CAMPAIGN,
    },
    {
        "id": "soc_manifest",
        "category": "test",
        "title": "Test — integration TB (manifest slaves)",
        "top": "tb_soc_manifest",
        "tb": "tb/tb_soc_manifest.v",
        "rtl": [*BUS_RTL, *SOC_CELL_RTL],
        "defines": ["+define+VERIF_MANIFEST_SOC_TB"],
        "headers": GEN_HEADERS_MANIFEST,
    },
    {
        "id": "soc_manifest_scale",
        "category": "test",
        "title": "Test — scale integration TB",
        "top": "tb_soc_manifest_scale",
        "tb": "tb/tb_soc_manifest_scale.v",
        "rtl": [*BUS_RTL, *SOC_CELL_RTL],
        "defines": ["+define+VERIF_MANIFEST_SCALE_TB"],
        "headers": GEN_HEADERS_MANIFEST_SCALE,
    },
    {
        "id": "chip_top_example",
        "category": "test",
        "title": "Test — chip top smoke",
        "top": "chip_top_example",
        "tb": "tb/chip_top_example.v",
        "rtl": [*BUS_RTL, *STUB_BUS_RTL, *SOC_CELL_RTL],
        "defines": ["+define+VERIF_CHIP_SOC_TB"],
        "headers": GEN_HEADERS_CHIP_TOP,
    },
]

EDA_VIEWS = EDA_WORK_VIEWS + EDA_TEST_VIEWS

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


def _flist_rel(category: str, name: str) -> str:
    """Relative path under filelists/ (e.g. work/rtl.f)."""
    base = WORK_DIR if category == "work" else TEST_DIR
    return f"{base.name}/{name}"


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
    cat = view.get("category", "test")
    combined = f"filelists/{cat}/verdi_{vid}.f"
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
        cat = view.get("category", "test")
        lines.append(
            f'  {view["id"]}) TOP="${{VERDI_TOP:-{view["top"]}}}"; '
            f'FLIST="filelists/{cat}/verdi_{view["id"]}.f" ;;'
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


def _eda_category(view: dict) -> str:
    return view.get("category", "test")


def _eda_view_prefix(view: dict) -> str:
    return f"eda/{_eda_category(view)}/{view['id']}"


def _emit_eda_view(view: dict, *, optional: set[str]) -> list[tuple[str, str]]:
    vid = view["id"]
    cat = _eda_category(view)
    out = (EDA_WORK_DIR if cat == "work" else EDA_TEST_DIR) / vid
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
        specs.append((f"{_eda_view_prefix(view)}/tb_top.list", "empty (integration DUT)"))

    for name, title, paths, note in files:
        (out / name).write_text(
            _emit_list_file(paths, title=title, note=note),
            encoding="utf-8",
        )
        specs.append((f"{_eda_view_prefix(view)}/{name}", title))

    (out / "defines.list").write_text(
        _emit_list_file(
            defines,
            title=f"Compile defines — {vid}",
            note="Optional; omit if your flow injects defines elsewhere",
            extras=[f"# TOP={top}"] + ([f"# {h}" for h in headers] if headers else []),
        ),
        encoding="utf-8",
    )
    specs.append((f"{_eda_view_prefix(view)}/defines.list", "defines + header deps (comments)"))

    (out / "top.txt").write_text(f"{top}\n", encoding="utf-8")
    specs.append((f"{_eda_view_prefix(view)}/top.txt", f"top module: {top}"))

    vcd = _VERDI_VCD.get(vid)
    if vcd:
        (out / "vcd.txt").write_text(f"{vcd}\n", encoding="utf-8")
        specs.append((f"{_eda_view_prefix(view)}/vcd.txt", "expected VCD path (after sim)"))

    # Master manifest — paths from package root (cwd = verif_cpu_verilog/)
    eda_prefix = f"filelists/{_eda_view_prefix(view)}"
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
    specs.append((f"{_eda_view_prefix(view)}/manifest.list", "ordered -F bundle"))

    return specs


def _eda_view_ids() -> str:
    return " ".join(v["id"] for v in EDA_VIEWS)


def _emit_eda_lib_sh() -> str:
    case_lines = []
    for v in EDA_VIEWS:
        case_lines.append(
            f'    {v["id"]}) echo "filelists/{_eda_view_prefix(v)}" ;;'
        )
    case_lines.append(
        '    integration_dut) echo "filelists/eda/work/integration" ;;'
    )
    case_body = "\n".join(case_lines)
    return "\n".join([
        "#!/usr/bin/env bash",
        "# Shared helpers for generated simulator run scripts.",
        "# Generated by tools/gen_filelist.py — do not edit.",
        "",
        f'EDA_VIEWS="{_eda_view_ids()}"',
        "",
        "eda_prefix() {",
        '  local view="$1"',
        "  case \"$view\" in",
        case_body,
        "    *)",
        '      echo "[eda] unknown view: $view" >&2',
        '      echo "[eda] views: $EDA_VIEWS" >&2',
        "      return 1 ;;",
        "  esac",
        "}",
        "",
        "eda_require_view() {",
        '  local view="$1"',
        '  local p',
        '  p="$(eda_prefix "$view")" || return 1',
        '  if [[ ! -f "$p/manifest.list" ]]; then',
        '    echo "[eda] missing $p/manifest.list — run: ./example.sh gen" >&2',
        "    return 1",
        "  fi",
        "}",
        "",
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
        'read -r -a IV_FLAGS <<< "$(eda_iverilog_f_flags "$VIEW")"',
        '"$IVERILOG" -g2012 "${IV_FLAGS[@]}" -s "$TOP" -o "$VVP_OUT"',
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
        'read -r -a VLT_INCDIRS <<< "$(eda_verilator_incdirs "$VIEW")"',
        'read -r -a VLT_DEFINES <<< "$(eda_verilator_defines "$VIEW")"',
        'echo "[verilator] view=$VIEW top=$TOP sources=${#SOURCES[@]} → $OUTDIR"',
        '"$VERILATOR" --binary -j 0 --timing \\',
        '  "${VLT_INCDIRS[@]}" \\',
        '  "${VLT_DEFINES[@]}" \\',
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
        'MANIFEST="$(eda_prefix "$VIEW")/manifest.list"',
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
        'XRUN_EXTRA=()',
        'if [[ -n "${XRUN_OPTS:-}" ]]; then',
        '  read -r -a XRUN_EXTRA <<< "$XRUN_OPTS"',
        'fi',
        '"$XRUN" -64bit -sv -timescale 1ns/1ps \\',
        '  -F "$MANIFEST" -top "$TOP" \\',
        '  -access +rwc -status \\',
        '  -xmlibdirname "$OUTDIR/xcelium.d" \\',
        '  -clean ${PROBE_TCL} "${XRUN_EXTRA[@]}"',
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


def _emit_scripts_makefile() -> str:
    return "\n".join([
        "# Generated by tools/gen_filelist.py — do not edit",
        ".PHONY: all filelists sim-scripts",
        "",
        "ROOT := $(abspath ..)",
        "",
        "all: filelists",
        "",
        "filelists sim-scripts:",
        "\t$(MAKE) -C $(ROOT) filelists",
        "",
    ])


def _emit_tools_makefile() -> str:
    return "\n".join([
        "# Generated by tools/gen_filelist.py — do not edit",
        ".PHONY: verify-vcd verify-amba",
        "",
        "ROOT := $(abspath ..)",
        "VCD_MAIN ?= $(ROOT)/sim_build/tb_full_campaign.vcd",
        "LOG_FULL ?= $(ROOT)/logs/full_campaign",
        "",
        "verify-vcd:",
        "\tpython3 verify_vcd.py $(VCD_MAIN) \\",
        "\t\t$(LOG_FULL)/SCPU1.vcd $(LOG_FULL)/SCPU2.vcd $(LOG_FULL)/SCPU3.vcd",
        "",
        "verify-amba:",
        "\tpython3 verify_amba_bus_vcd.py \\",
        "\t\t$(ROOT)/sim_build/tb_soc_bus_all.vcd \\",
        "\t\t$(ROOT)/sim_build/tb_soc_bus_bridge.vcd",
        "",
    ])


def _generate_aux_makefiles() -> None:
    (SCRIPTS_DIR / "Makefile").write_text(_emit_scripts_makefile(), encoding="utf-8")
    (ROOT / "tools" / "Makefile").write_text(_emit_tools_makefile(), encoding="utf-8")


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
    _generate_aux_makefiles()


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
        'MANIFEST="$(eda_prefix "$VIEW")/manifest.list"',
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
        'MANIFEST="$(eda_prefix "$VIEW")/manifest.list"',
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


def _clean_stale_eda_flat() -> None:
    """Drop legacy eda/<view>/ dirs (before work/test split)."""
    if not EDA_DIR.is_dir():
        return
    keep = {"work", "test", "README.txt"}
    for child in EDA_DIR.iterdir():
        if child.name in keep or not child.is_dir():
            continue
        shutil.rmtree(child)


def _write_category_readme(path: Path, *, title: str, body: list[str]) -> None:
    path.write_text(
        "\n".join([f"# {title}", ""] + body + [""]),
        encoding="utf-8",
    )


def _write_flist(
    dest: Path,
    rel_spec: str,
    *,
    title: str,
    rtl: list[str],
    tb: str | None = None,
    defines: list[str] | None = None,
    headers: list[str] | None = None,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = _emit_files(
        rtl,
        title=title,
        note=f"iverilog: iverilog -g2012 -f filelists/incdirs.f -f filelists/{rel_spec}",
        tb=tb,
        defines=defines,
        headers=headers,
    )
    dest.write_text(text, encoding="utf-8")


def _root_alias(name: str, target: str, title: str) -> str:
    text = "\n".join([
        f"// Legacy alias — use filelists/{target}",
        f"// {title}",
        f"// iverilog -g2012 -f filelists/incdirs.f -f filelists/{target}",
        "",
    ])
    (OUT_DIR / name).write_text(text, encoding="utf-8")
    return f"{name} → {target}"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    opt = set(GEN_HEADERS_COMMON + GEN_HEADERS_CAMPAIGN + GEN_HEADERS_MANIFEST
              + GEN_HEADERS_MANIFEST_SCALE + GEN_HEADERS_CHIP_TOP + FW_ARTIFACTS
              + SOC_CELL_RTL)

    specs: list[tuple[str, str]] = []

    (OUT_DIR / "incdirs.f").write_text("\n".join(_emit_incdirs()), encoding="utf-8")
    specs.append(("incdirs.f", "shared include dirs"))

    work_groups = [
        (
            "vcpu.f",
            "Work — VCPU IP (core + pool + orchestrator + agent)",
            _check_paths(VCPU_STACK, opt),
            None,
            None,
            None,
        ),
        (
            "rtl.f",
            "Work — real SoC attach (vcpu + bridges + soc_cell + connect VH)",
            _check_paths(RTL_INTEGRATION, opt),
            None,
            None,
            RTL_CONNECT_HEADERS,
        ),
    ]
    test_groups = [
        (
            "tb_dut.f",
            "Test — internal regression (rtl + simple_soc + tb_full_campaign)",
            _check_paths(TB_DUT_RTL, opt),
            "tb/tb_full_campaign.v",
            None,
            GEN_HEADERS_CAMPAIGN + FW_ARTIFACTS,
        ),
        (
            "soc_manifest.f",
            "Test — bridge wiring reference (tb_soc_manifest)",
            _check_paths(RTL_INTEGRATION, opt),
            "tb/tb_soc_manifest.v",
            ["+define+VERIF_MANIFEST_SOC_TB"],
            GEN_HEADERS_MANIFEST + FW_ARTIFACTS,
        ),
    ]

    for name, title, rtl, tb, defines, headers in work_groups:
        rel = f"work/{name}"
        _write_flist(
            WORK_DIR / name, rel,
            title=title, rtl=rtl, tb=tb, defines=defines, headers=headers,
        )
        specs.append((rel, title))

    for name, title, rtl, tb, defines, headers in test_groups:
        rel = f"test/{name}"
        _write_flist(
            TEST_DIR / name, rel,
            title=title, rtl=rtl, tb=tb, defines=defines, headers=headers,
        )
        specs.append((rel, title))

    for alias_line in (
        _root_alias("vcpu.f", "work/vcpu.f", "moved to work/"),
        _root_alias("rtl.f", "work/rtl.f", "moved to work/"),
        _root_alias("tb_dut.f", "test/tb_dut.f", "moved to test/"),
        _root_alias("integration_dut.f", "work/rtl.f", "same as work/rtl.f"),
        _root_alias("full_campaign.f", "test/tb_dut.f", "same as test/tb_dut.f"),
        _root_alias("soc_manifest.f", "test/soc_manifest.f", "moved to test/"),
    ):
        specs.append((alias_line.split(" → ")[0], alias_line))

    # Verdi combined imports under work/ or test/
    for view in VERDI_VIEWS:
        src = view["flist"]
        src_path = OUT_DIR / src
        if not src_path.is_file():
            continue
        cat = view.get("category", "test")
        combined_rel = f"{cat}/verdi_{view['id']}.f"
        combined_path = (WORK_DIR if cat == "work" else TEST_DIR) / f"verdi_{view['id']}.f"
        combined_path.write_text(
            _emit_verdi_combined(src, top=view["top"]),
            encoding="utf-8",
        )
        specs.append((combined_rel, f"Verdi — {view['title']}"))

    _write_category_readme(
        WORK_DIR / "README.txt",
        title="work — 회사 SoC 통합 (TB 없음)",
        body=[
            "vcpu.f  VCPU IP만",
            "rtl.f   vcpu + AMBA bridge + verif_vcpu_soc_cell (+ connect.vh)",
            "",
            "iverilog -g2012 -f filelists/incdirs.f -f filelists/work/rtl.f",
            "VCS/xrun view: integration  (filelists/eda/work/integration/)",
        ],
    )
    _write_category_readme(
        TEST_DIR / "README.txt",
        title="test — 패키지 내부 검증·참고",
        body=[
            "tb_dut.f        ./example.sh sim (simple_soc + full_campaign)",
            "soc_manifest.f  make soc-manifest (real bridge 배선 참고)",
            "",
            "iverilog -g2012 -f filelists/incdirs.f -f filelists/test/tb_dut.f",
        ],
    )

    # EDA split lists (VCS / Xcelium)
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    _clean_stale_eda_flat()
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
        "# Run from verif_cpu_verilog/",
        "",
        "# === work/  (회사 SoC 통합용 — TB 없음) ===",
        "#   work/vcpu.f   VCPU IP만",
        "#   work/rtl.f    vcpu + AMBA bridge + soc_cell (+ connect.vh)",
        "#   iverilog -g2012 -f filelists/incdirs.f -f filelists/work/rtl.f",
        "",
        "# === test/  (패키지 내부 검증·참고 TB) ===",
        "#   test/tb_dut.f        ./example.sh sim (simple_soc + full_campaign)",
        "#   test/soc_manifest.f  make soc-manifest (bridge 배선 참고)",
        "",
        "# EDA split: filelists/eda/work/integration/*.list",
        "#             filelists/eda/test/<view>/*.list",
        "",
    ]
    for name, title in specs:
        if name.endswith(".f") or "/" in name:
            index_lines.append(f"#   {name:<32} {title}")
    index_lines.extend([
        "",
        "# Verdi: ./scripts/verdi/rtl.sh | full_campaign.sh | soc_manifest.sh",
        "",
    ])
    (OUT_DIR / "README.txt").write_text("\n".join(index_lines), encoding="utf-8")

    for stale in (
        "verdi_full_campaign.f",
        "verdi_rtl.f",
        "verdi_soc_manifest.f",
    ):
        p = OUT_DIR / stale
        if p.is_file():
            p.unlink()

    print(f"[filelist] Wrote {OUT_DIR}/ ({len(specs)} lists)")
    for name, _ in specs:
        print(f"  {OUT_DIR / name}")
    print(f"[filelist] EDA work → {EDA_WORK_DIR}/")
    print(f"[filelist] EDA test → {EDA_TEST_DIR}/")
    for view in EDA_VIEWS:
        print(f"  {EDA_DIR / _eda_category(view) / view['id']}/{{vcpu,rtl,tb_top}}.list")
    print(f"[filelist] Verdi launchers → {VERDI_DIR}/")
    for view in VERDI_VIEWS:
        print(f"  {VERDI_DIR / (view['id'] + '.sh')}")
    print("[filelist] Simulator run scripts → scripts/{iverilog,verilator,vcs,xcelium}/run.sh")
    print(f"  {SCRIPTS_DIR / 'README.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())