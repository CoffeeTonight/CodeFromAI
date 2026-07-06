#!/usr/bin/env python3
"""Remove artifacts produced by ./example.sh gen / sim.

Keeps hand-written sources (campaign_slots.yaml, soc_regs.h, harness *.hex, …).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# firmware/campaign — generated C headers (not soc_regs.h / soc_platform.h / …)
GEN_FW_HDRS = [
    "firmware/campaign/include/campaign_manifest.h",
    "firmware/campaign/include/campaign_layout.h",
    "firmware/campaign/include/icode_map.h",
    "firmware/campaign/include/icode_map.json",
]

GEN_FW_MK = [
    "firmware/campaign/cpus.mk",
    "firmware/campaign/cpu_rules.mk",
    "firmware/campaign/icodes/icodes.mk",
    "firmware/campaign/.bus_layout_stamp",
    "firmware/campaign/build/.icodes.stamp",
    "firmware/campaign/build/.fw_default.stamp",
    "firmware/campaign/build/.fw_scale.stamp",
]

GEN_FW_HEX = [
    "firmware/full_campaign_unified.hex",
    "firmware/full_campaign_vcpu.hex",
]

# ../../include — generated Verilog headers
GEN_VH = [
    "include/campaign_params.vh",
    "include/campaign_master.vh",
    "include/campaign_scale.vh",
    "include/campaign_manifest.vh",
    "include/campaign_soc_platform.vh",
    "include/soc_init_seq.vh",
    "include/icode_map.vh",
    "include/icode_bind.vh",
    "include/tb_full_campaign_gen.vh",
    "include/tb_soc_manifest_defs.vh",
    "include/tb_soc_manifest_gen.vh",
    "include/tb_soc_manifest_decode.vh",
    "include/tb_soc_manifest_scale_defs.vh",
    "include/tb_soc_manifest_scale_gen.vh",
    "include/verif_manifest_soc_bus_read.vh",
    "include/verif_manifest_soc_bus_write.vh",
    "include/verif_manifest_scale_soc_bus_read.vh",
    "include/verif_manifest_scale_soc_bus_write.vh",
    "include/verif_chip_soc_bus_read.vh",
    "include/verif_chip_soc_bus_write.vh",
    "include/chip_top_example_gen.vh",
    "include/chip_top_decode.vh",
    "include/verif_soc_bus_connect.vh",
]

GEN_RTL = [
    "rtl/verif_vcpu_soc_cell.v",
]

GEN_DIRS = [
    "firmware/campaign/build",
    "sim_build",
    "logs",
    "filelists",
    "scripts",
]


def _rm_file(path: Path, *, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    if dry_run:
        print(f"  would remove file {path.relative_to(ROOT)}")
    else:
        path.unlink()
        print(f"  removed file {path.relative_to(ROOT)}")
    return True


def _rm_tree(path: Path, *, dry_run: bool) -> bool:
    if not path.exists():
        return False
    if dry_run:
        print(f"  would remove tree {path.relative_to(ROOT)}/")
    else:
        shutil.rmtree(path)
        print(f"  removed tree {path.relative_to(ROOT)}/")
    return True


def clean(*, fw_only: bool, dry_run: bool) -> int:
    removed = 0

    for rel in GEN_FW_HDRS + GEN_FW_MK + GEN_FW_HEX:
        if _rm_file(ROOT / rel, dry_run=dry_run):
            removed += 1

    if _rm_tree(ROOT / "firmware/campaign/build", dry_run=dry_run):
        removed += 1

    probe_dir = ROOT / "firmware/campaign/icodes/probe"
    if probe_dir.is_dir():
        for path in sorted(probe_dir.glob("*.c")):
            if _rm_file(path, dry_run=dry_run):
                removed += 1

    if fw_only:
        print(f"[clean_generated] fw scope: {removed} item(s)")
        return 0

    for rel in GEN_VH + GEN_RTL:
        if _rm_file(ROOT / rel, dry_run=dry_run):
            removed += 1

    for rel in GEN_DIRS:
        if rel == "firmware/campaign/build":
            continue
        if _rm_tree(ROOT / rel, dry_run=dry_run):
            removed += 1

    print(f"[clean_generated] full scope: {removed} item(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove example.sh gen/sim artifacts")
    parser.add_argument(
        "--fw-only",
        action="store_true",
        help="firmware/campaign build + generated C headers only",
    )
    parser.add_argument("-n", "--dry-run", action="store_true")
    args = parser.parse_args()
    return clean(fw_only=args.fw_only, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())