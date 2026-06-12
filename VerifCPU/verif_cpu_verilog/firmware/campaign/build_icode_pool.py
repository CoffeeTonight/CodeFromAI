#!/usr/bin/env python3
"""
Build icode pool end-to-end:
  1) make -C icodes        (compile all icodes/*.c → build/icodes/*.bin)
  2) merge                 → build/icode_pool.bin
  3) probe (tinyrv via requirements.txt; static decode fallback) → icode_map headers
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CAMPAIGN_ROOT = Path(__file__).resolve().parent
ICODES_DIR = CAMPAIGN_ROOT / "icodes"
BIN_DIR = CAMPAIGN_ROOT / "build" / "icodes"
POOL_BIN = CAMPAIGN_ROOT / "build" / "icode_pool.bin"
HDR_OUT = CAMPAIGN_ROOT / "include" / "icode_map.h"
JSON_OUT = CAMPAIGN_ROOT / "include" / "icode_map.json"
VERILOG_ROOT = CAMPAIGN_ROOT.parent.parent
VH_MAP = VERILOG_ROOT / "include" / "icode_map.vh"
VH_BIND = VERILOG_ROOT / "include" / "icode_bind.vh"
MANIFEST_HDR = CAMPAIGN_ROOT / "include" / "campaign_manifest.h"

TOOLS = VERILOG_ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from probe_icodes import (  # noqa: E402
    IcodeImage,
    assign_pool_ptrs,
    discover_bins,
    emit_icode_bind_vh,
    emit_icode_map_h,
    emit_icode_map_json,
    emit_icode_map_vh,
    merge_icode_pool,
    probe_images,
)


def run_gen_sources() -> None:
    gen = CAMPAIGN_ROOT / "gen_icodes_c.py"
    print("[1/4] Generating icode C sources (catalog-50)...")
    subprocess.run([sys.executable, str(gen)], check=True)


def run_make() -> None:
    print("[2/4] Compiling icodes (make -C icodes)...")
    subprocess.run(["make", "-C", str(ICODES_DIR)], check=True)


def load_images() -> list[IcodeImage]:
    if not BIN_DIR.is_dir():
        raise FileNotFoundError(f"missing bin dir: {BIN_DIR}")

    pairs = discover_bins(BIN_DIR)
    if not pairs:
        raise FileNotFoundError(f"no .bin files in {BIN_DIR}")

    names = [n for n, _ in pairs]
    ptrs = assign_pool_ptrs(names)
    images: list[IcodeImage] = []
    for name, path in pairs:
        blob = path.read_bytes()
        images.append(IcodeImage(name=name, pool_ptr=ptrs[name], blob=blob))
    return images


def main() -> int:
    parser = argparse.ArgumentParser(description="Build icode pool + probe mapping header")
    parser.add_argument("--skip-make", action="store_true", help="Skip compile step (reuse bins)")
    args = parser.parse_args()

    if not args.skip_make:
        run_gen_sources()
        run_make()
    else:
        print("[1/5] Skipping compile (--skip-make)")

    images = load_images()
    print(f"[3/4] Merging {len(images)} icodes → {POOL_BIN.name}")
    pool = merge_icode_pool(images)
    POOL_BIN.parent.mkdir(parents=True, exist_ok=True)
    POOL_BIN.write_bytes(pool)
    print(f"       pool size = {len(pool)} bytes ({len(images)} slots)")

    print("[4/4] Probing icodes + emitting mapping header...")
    entries = probe_images(images)
    emit_icode_map_h(HDR_OUT, entries, len(pool))
    emit_icode_map_json(JSON_OUT, entries, len(pool))
    emit_icode_map_vh(VH_MAP, entries, len(pool))
    emit_icode_bind_vh(VH_BIND, MANIFEST_HDR, entries)

    print("[5/5] Generating tb_full_campaign_gen.vh...")
    gen_tb = CAMPAIGN_ROOT / "gen_tb_campaign.py"
    subprocess.run([sys.executable, str(gen_tb)], check=True)

    print("")
    print("=== icode pool build complete ===")
    for e in entries:
        print(
            f"  {e.name:24s} ptr=0x{e.pool_ptr:08x} "
            f"{e.bus_op}@0x{e.bus_addr:08x} tap={e.tap_port} ({e.bin_bytes} B)"
        )
    print(f"\n  {POOL_BIN}")
    print(f"  {HDR_OUT}")
    print(f"  {JSON_OUT}")
    print(f"  {VH_MAP}")
    print(f"  {VH_BIND}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())