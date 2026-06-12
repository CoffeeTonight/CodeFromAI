#!/usr/bin/env python3
"""Merge campaign CPU .bin images; embed icode pool when small (readmemh), else lazy file."""

import json
import os
import re
import struct
import sys

from verilog_paths import BUILD_DIR as BUILD, CAMPAIGN_ROOT as ROOT, FIRMWARE_DIR

CPUS_MK = os.path.join(ROOT, "cpus.mk")
OUT_VCPU_BIN = os.path.join(BUILD, "full_campaign_vcpu.bin")
OUT_VCPU_HEX = os.path.join(FIRMWARE_DIR, "full_campaign_vcpu.hex")
OUT_UNIFIED_BIN = os.path.join(BUILD, "full_campaign_unified.bin")
OUT_UNIFIED_HEX = os.path.join(FIRMWARE_DIR, "full_campaign_unified.hex")
ICODE_POOL_BIN = os.path.join(BUILD, "icode_pool.bin")
ICODE_JSON = os.path.join(ROOT, "include", "icode_map.json")

from campaign_pool_policy import (  # noqa: E402
    POOL_READMEMH_MAX_BYTES,
    POOL_WORD_ICODE,
    VCPU_IMAGE_BYTES,
    icode_use_lazy,
    unified_image_bytes,
)


REGION_SIZE = 0x2000


NOOP_BIN = os.path.join(BUILD, "NOOP.bin")


def parse_cpus_mk():
    cpus = []
    with open(CPUS_MK, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or not line.startswith("CPU_"):
                continue
            if line.startswith(("CPU_NAMES", "CPU_ACTIVE")) or ":=" not in line:
                continue
            name = re.search(r"name=([^\s]+)", line)
            cid = re.search(r"id=(\d+)", line)
            pool = re.search(r"pool_word=(0x[0-9a-fA-F]+)", line)
            enabled = re.search(r"enabled=([01])", line)
            if name and cid and pool:
                is_on = enabled.group(1) == "1" if enabled else True
                bin_path = (
                    os.path.join(BUILD, f"{name.group(1)}.bin")
                    if is_on
                    else NOOP_BIN
                )
                cpus.append({
                    "name": name.group(1),
                    "id": int(cid.group(1)) if cid else 0,
                    "pool_word": int(pool.group(1), 16),
                    "enabled": is_on,
                    "bin": bin_path,
                })
    return cpus


def pool_bytes_from_json() -> int:
    with open(ICODE_JSON, encoding="utf-8") as f:
        return int(json.load(f)["pool_bytes"])


def write_hex(path: str, mem: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pad = (4 - len(mem) % 4) % 4
    padded = mem + (b"\x00" * pad)
    with open(path, "w", encoding="utf-8") as f:
        for i in range(0, len(padded), 4):
            word = struct.unpack_from("<I", padded, i)[0]
            f.write(f"{word:08x}\n")


def main() -> int:
    cpus = parse_cpus_mk()
    if not cpus:
        print("[merge] no VCPU firmware in cpus.mk — orchestrator-only image")

    if not os.path.isfile(ICODE_POOL_BIN):
        print(f"[merge] missing {ICODE_POOL_BIN} — run build_icode_pool.py first", file=sys.stderr)
        return 1

    pool_bytes = pool_bytes_from_json()
    use_lazy = icode_use_lazy(pool_bytes)
    mode = "lazy file-backed" if use_lazy else "readmemh embed"

    mem = bytearray(VCPU_IMAGE_BYTES)
    print(f"[merge] VCPU image + icode policy (pool={pool_bytes} B, max embed={POOL_READMEMH_MAX_BYTES} B → {mode})")
    for cpu in cpus:
        path = cpu["bin"]
        if not os.path.isfile(path):
            print(f"[merge] missing {path}", file=sys.stderr)
            return 1
        with open(path, "rb") as f:
            blob = f.read()
        if len(blob) > REGION_SIZE:
            print(f"[merge] {cpu['name']} exceeds {REGION_SIZE} bytes", file=sys.stderr)
            return 1
        base_byte = cpu["pool_word"] * 4
        if base_byte + len(blob) > len(mem):
            print(f"[merge] {cpu['name']} overflows VCPU image", file=sys.stderr)
            return 1
        mem[base_byte : base_byte + len(blob)] = blob
        print(f"  [{cpu['name']:4s}] pool_word=0x{cpu['pool_word']:04x} "
              f"({len(blob)} bytes) <- {path}")

    with open(ICODE_POOL_BIN, "rb") as f:
        icode_blob = f.read()

    os.makedirs(BUILD, exist_ok=True)
    with open(OUT_VCPU_BIN, "wb") as f:
        f.write(mem)
    write_hex(OUT_VCPU_HEX, mem)
    print(f"[merge] Wrote {OUT_VCPU_BIN} ({len(mem)} bytes)")
    print(f"[merge] Wrote {OUT_VCPU_HEX} ({len(mem) // 4} words)")

    if use_lazy:
        print(f"  [ICODE] separate: {ICODE_POOL_BIN} ({len(icode_blob)} bytes)")
    else:
        img_bytes = unified_image_bytes(pool_bytes)
        unified = bytearray(img_bytes)
        unified[: len(mem)] = mem
        icode_base = POOL_WORD_ICODE * 4
        if icode_base + len(icode_blob) > len(unified):
            print("[merge] icode pool overflows unified image", file=sys.stderr)
            return 1
        unified[icode_base : icode_base + len(icode_blob)] = icode_blob
        with open(OUT_UNIFIED_BIN, "wb") as f:
            f.write(unified)
        write_hex(OUT_UNIFIED_HEX, unified)
        print(f"  [ICODE] embedded @ word 0x{POOL_WORD_ICODE:x} ({len(icode_blob)} bytes)")
        print(f"[merge] Wrote {OUT_UNIFIED_BIN} ({len(unified)} bytes)")
        print(f"[merge] Wrote {OUT_UNIFIED_HEX} ({len(unified) // 4} words)")

    return 0


if __name__ == "__main__":
    sys.exit(main())