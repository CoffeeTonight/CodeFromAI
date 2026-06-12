#!/usr/bin/env python3
"""VerifCPU Verilog model — generate firmware artifacts and run authoritative campaign.

Python equivalent of example.sh. Same commands, env vars, and gen/bus-layout parsing.

Usage:
  ./example.py              # gen + full_campaign (default)
  ./example.py gen 64
  ./example.py gen --axi 62 --ahb 1 --apb 1
  ./example.py all 64
  ./example.py sim
  ./example.py manifest
  ./example.py chip-top
  ./example.py vcd
  ./example.py clean
  ./example.py help
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FW = ROOT / "firmware" / "campaign"
LOG_FULL = Path(os.environ.get("LOG_FULL", ROOT / "logs" / "full_campaign"))
VCD_MAIN = ROOT / "sim_build" / "tb_full_campaign.vcd"
PARAMS_VH = ROOT / "include" / "campaign_params.vh"

sys.path.insert(0, str(FW))
from amba_bus_registry import CLI_FLAG_TO_BUS  # noqa: E402


def die(msg: str, code: int = 1) -> None:
    print(f"[example.py] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def need_cmd(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"missing command: {name}")
    return path


def step(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    subprocess.run(cmd, cwd=cwd or ROOT, env=merged, check=True)


def ensure_py_deps() -> None:
    req = ROOT / "requirements.txt"
    if not req.is_file():
        die(f"missing {req}")
    need_cmd("python3")
    print("[deps] python3 -m pip install -r requirements.txt (tinyrv, PyYAML)")
    run([sys.executable, "-m", "pip", "install", "-r", str(req)])


def read_default_num_scpu() -> str:
    if not PARAMS_VH.is_file():
        return "default"
    for line in PARAMS_VH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*`define\s+CAMPAIGN_NUM_SCPU\s+(\d+)", line)
        if m:
            return m.group(1)
    return "default"


def parse_num_scpu(arg: str | None) -> None:
    if not arg:
        return
    if not arg.isdigit():
        die(f"invalid slave SCPU count: '{arg}' (use: ./example.py gen 64)")
    n = int(arg)
    if n < 0 or n > 256:
        die(f"NUM_SCPU out of range: {arg} (allowed 0..256; 0 = solo MVCPU)")
    os.environ["NUM_SCPU"] = str(n)
    print(f"[example.py] CAMPAIGN_NUM_SCPU={n}")


def parse_gen_args(argv: list[str]) -> None:
    layout_parts: list[str] = []
    layout_total = 0
    positional: str | None = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in CLI_FLAG_TO_BUS:
            if i + 1 >= len(argv) or not argv[i + 1].isdigit():
                die(f"expected count after {a} (e.g. {a} 62; use 0 for none)")
            count = int(argv[i + 1])
            kind = CLI_FLAG_TO_BUS[a]
            layout_parts.append(f"{kind}:{count}")
            layout_total += count
            i += 2
            continue
        if a == "--master-enabled":
            if i + 1 >= len(argv):
                die("expected 0 or 1 after --master-enabled")
            os.environ["MASTER_ENABLED"] = argv[i + 1]
            i += 2
            continue
        if a == "--master-bus":
            if i + 2 >= len(argv) or not argv[i + 2].isdigit():
                die("expected --master-bus <bus-flag> <count> (e.g. --master-bus --axi 1)")
            bus_flag = argv[i + 1]
            if bus_flag not in CLI_FLAG_TO_BUS:
                die(f"unknown master bus flag: {bus_flag}")
            os.environ["MASTER_BUS_LAYOUT"] = f"{CLI_FLAG_TO_BUS[bus_flag]}:{argv[i + 2]}"
            i += 3
            continue
        if a.startswith("--"):
            die(f"unknown gen flag: {a} (see amba_bus_registry.py / ./example.py help)")
        if a.isdigit():
            if positional is not None:
                die(f"ambiguous gen args: multiple positional counts ({positional}, {a})")
            positional = a
            i += 1
            continue
        die(f"unexpected gen argument: {a}")
        i += 1

    if layout_parts:
        if layout_total < 0 or layout_total > 256:
            die(f"bus layout total out of range: {layout_total} (allowed 0..256)")
        os.environ["BUS_LAYOUT"] = ",".join(layout_parts)
        os.environ["NUM_SCPU"] = str(layout_total)
        print(
            f"[example.py] BUS_LAYOUT={os.environ['BUS_LAYOUT']} "
            f"→ CAMPAIGN_NUM_SCPU={layout_total}"
        )
        if layout_total == 0:
            print("[example.py] solo mode — master.enabled defaults to 1")
            if not os.environ.get("MASTER_ENABLED"):
                os.environ["MASTER_ENABLED"] = "1"
        if positional is not None and int(positional) != layout_total:
            die(f"positional count {positional} disagrees with bus layout total {layout_total}")
        return

    os.environ.pop("BUS_LAYOUT", None)
    if positional is not None:
        parse_num_scpu(positional)
    elif os.environ.get("NUM_SCPU"):
        parse_num_scpu(os.environ["NUM_SCPU"])


def _make_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("NUM_SCPU", "BUS_LAYOUT", "MASTER_BUS_LAYOUT", "MASTER_ENABLED"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def run_gen() -> None:
    if not os.environ.get("NUM_SCPU") and not os.environ.get("BUS_LAYOUT"):
        os.environ["NUM_SCPU"] = "3"
        print("[example.py] default CAMPAIGN_NUM_SCPU=3 (yaml active slaves)")
    slots = os.environ.get("NUM_SCPU") or read_default_num_scpu()
    step(f"[1/2] Generate campaign firmware + Verilog headers (NUM_SCPU={slots})")
    if not FW.is_dir():
        die(f"firmware dir not found: {FW}")
    ensure_py_deps()

    mk_env = _make_env()
    print(f"[gen] config    → CAMPAIGN_NUM_SCPU={slots} → manifest, cpus.mk, campaign_scale.vh")
    if mk_env:
        args = ["make", "config"]
        for key in ("NUM_SCPU", "BUS_LAYOUT", "MASTER_BUS_LAYOUT", "MASTER_ENABLED"):
            if mk_env.get(key):
                args.append(f"{key}={mk_env[key]}")
        run(args, cwd=FW, env=mk_env)
    else:
        run(["make", "config"], cwd=FW)

    gen_env = {**os.environ, **mk_env}

    print("[gen] soc_init  → soc_init_seq.vh, campaign_soc_platform.vh")
    run(["make", "soc_init"], cwd=FW, env=gen_env)

    print("[gen] manifest  → campaign_manifest.vh")
    run(["make", "manifest"], cwd=FW, env=gen_env)

    print("[gen] icodes    → icode_pool.bin, icode_map.vh, tb_full_campaign_gen.vh")
    run(["make", "icodes"], cwd=FW, env=gen_env)

    if mk_env.get("BUS_LAYOUT") or mk_env.get("MASTER_BUS_LAYOUT"):
        print("[gen] bus_connect → verif_soc_bus_connect.vh (manifest bus ports)")
        run(["make", "bus_connect"], cwd=FW, env=gen_env)

    print("[gen] VCPU bins + merge → full_campaign_unified.hex")
    run(["make", "all"], cwd=FW, env=gen_env)

    print("[gen] filelists + sim scripts → eda/*/*.list, scripts/{iverilog,verilator,vcs,xcelium,verdi}/")
    run(["make", "filelists"])

    print()
    print("[gen] Artifacts:")
    build = FW / "build"
    if build.is_dir():
        for p in sorted(build.glob("*.bin")):
            print(f"  {p}")
    for p in sorted((ROOT / "firmware").glob("*.hex")):
        print(f"  {p}")
    for name in ("tb_full_campaign_gen.vh", "icode_map.vh", "campaign_manifest.vh"):
        p = ROOT / "include" / name
        if p.is_file():
            print(f"  {p}")
    flist = ROOT / "filelists"
    if flist.is_dir():
        for p in sorted(flist.glob("*.f"))[:16]:
            print(f"  {p}")
    verdi = ROOT / "scripts" / "verdi"
    if verdi.is_dir():
        for p in sorted(verdi.glob("*.sh"))[:8]:
            print(f"  {p}")


def run_sim() -> None:
    step("[2/2] iverilog full_campaign (authoritative gate)")
    need_cmd("iverilog")
    need_cmd("vvp")
    need_cmd("python3")
    LOG_FULL.mkdir(parents=True, exist_ok=True)
    run(["make", "full_campaign"])
    print()
    print("[sim] VCD artifacts:")
    print(f"  Main : {VCD_MAIN}")
    for cid in (1, 2, 3):
        p = LOG_FULL / f"SCPU{cid}.vcd"
        if p.is_file():
            print(f"  CPU{cid}: {p} ({p.stat().st_size} bytes)")


def run_soc_manifest() -> None:
    step("iverilog soc-manifest (integration TB — real AMBA bridges)")
    need_cmd("iverilog")
    need_cmd("vvp")
    run(["make", "soc-manifest"])


def run_chip_top() -> None:
    step("iverilog chip-top-example (soc_hierarchy yaml compile smoke)")
    need_cmd("iverilog")
    need_cmd("vvp")
    run(["make", "chip-top-example"])


def run_vcd_only() -> None:
    step("VCD post-check (verify_vcd.py)")
    need_cmd("python3")
    if not VCD_MAIN.is_file():
        die(f"missing main VCD: {VCD_MAIN} (run ./example.py sim first)")
    run([
        sys.executable,
        str(ROOT / "tools" / "verify_vcd.py"),
        str(VCD_MAIN),
        str(LOG_FULL / "SCPU1.vcd"),
        str(LOG_FULL / "SCPU2.vcd"),
        str(LOG_FULL / "SCPU3.vcd"),
    ])


def run_verdi(view: str = "full_campaign", *wave_args: str) -> None:
    step(f"Verdi — view={view} (source + VCD if sim already ran)")
    script = ROOT / "scripts" / "verdi" / f"{view}.sh"
    if not script.is_file():
        die(f"missing {script} — run: ./example.py gen")
    cmd = [str(script), *wave_args]
    os.execv(str(script), cmd)


def run_clean() -> None:
    step("Clean verification artifacts (sim_build, logs, campaign build)")
    run(["make", "clean-artifacts"])
    print("[clean] done — regenerate with: ./example.py gen")


HELP_TEXT = """\
VerifCPU Verilog example runner (Python)

Commands:
  (none)|all [N]   Generate firmware + run full_campaign (+ optional N slave SCPU)
  gen [N]          Generation only; N = slave SCPU count (SCPU1..N), e.g. gen 64
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
  LOG_FULL     Per-CPU VCD log directory (default: .../logs/full_campaign)

Examples:
  ./example.py
  ./example.py gen 64
  ./example.py gen --axi 62 --ahb 1 --apb 1
  ./example.py gen --apb 1 --axi 62 --ahb 1
  ./example.py all 64
  ./example.py gen && ./example.py sim
  ./example.py verdi
  ./example.py verdi soc_manifest_scale
  NUM_SCPU=40 ./example.py gen
  LOG_FULL=/tmp/vcd ./example.py sim
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="example.py",
        description="VerifCPU Verilog campaign runner (Python port of example.sh)",
        add_help=False,
    )
    p.add_argument(
        "command",
        nargs="?",
        default="all",
        help="all|gen|sim|manifest|chip-top|vcd|verdi|clean|help",
    )
    p.add_argument("rest", nargs=argparse.REMAINDER, help="gen args: N or --axi N …")
    p.add_argument("-h", "--help", action="store_true", help="show help and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.help:
        print(HELP_TEXT)
        return 0

    cmd = args.command
    rest = list(args.rest)
    if rest and rest[0] == "--help":
        print(HELP_TEXT)
        return 0

    gen_cmds = {"all", "full", "verify", "gen", "generate"}
    if cmd in gen_cmds:
        parse_gen_args(rest)

    dispatch = {
        "all": lambda: (run_gen(), run_sim()),
        "full": lambda: (run_gen(), run_sim()),
        "verify": lambda: (run_gen(), run_sim()),
        "gen": run_gen,
        "generate": run_gen,
        "sim": run_sim,
        "run": run_sim,
        "simulate": run_sim,
        "manifest": run_soc_manifest,
        "soc-manifest": run_soc_manifest,
        "chip-top": run_chip_top,
        "chip-top-example": run_chip_top,
        "vcd": run_vcd_only,
        "check-vcd": run_vcd_only,
        "verdi": lambda: run_verdi(*(rest or ["full_campaign"])),
        "verdi-gui": lambda: run_verdi(*(rest or ["full_campaign"])),
        "gui": lambda: run_verdi(*(rest or ["full_campaign"])),
        "clean": run_clean,
        "help": lambda: print(HELP_TEXT),
        "-h": lambda: print(HELP_TEXT),
        "--help": lambda: print(HELP_TEXT),
    }

    fn = dispatch.get(cmd)
    if fn is None:
        die(f"unknown command: {cmd} (try: ./example.py help)")
    fn()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        die(f"command failed (exit {exc.returncode}): {' '.join(exc.cmd)}", exc.returncode)