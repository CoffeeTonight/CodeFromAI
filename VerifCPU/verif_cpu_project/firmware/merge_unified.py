#!/usr/bin/env python3
"""
Merge multiple CPU .bin files into one unified memory image.

Usage:
    python merge_unified.py

It reads cpus.mk to know the start_offset for each CPU, then creates
a single binary (unified_memory.bin) with proper padding.

This is useful when you have one big memory space and each CPU's
firmware is placed at a specific offset.
"""

import os
import re
from pathlib import Path

CPUS_MK = "cpus.mk"
BUILD_DIR = "build"
OUTPUT_FILE = "build/unified_memory.bin"
DEFAULT_SIZE = 0x100000  # 1MB default unified memory size

def parse_cpus_mk():
    cpus = []
    if not os.path.exists(CPUS_MK):
        print(f"Error: {CPUS_MK} not found")
        return cpus

    with open(CPUS_MK, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("CPU_"):
                # Extract fields
                match = re.search(r'name=([^\s]+)', line)
                name = match.group(1) if match else None

                match = re.search(r'id=(\d+)', line)
                cpu_id = int(match.group(1)) if match else None

                match = re.search(r'start_offset=(0x[0-9a-fA-F]+)', line)
                offset = int(match.group(1), 16) if match else None

                if name and offset is not None:
                    bin_path = Path(BUILD_DIR) / f"CPU_{name}.bin"
                    if not bin_path.exists():
                        bin_path = Path(BUILD_DIR) / f"{name}.bin"  # fallback

                    cpus.append({
                        "name": name,
                        "id": cpu_id,
                        "offset": offset,
                        "bin": bin_path
                    })
    return cpus

def main():
    cpus = parse_cpus_mk()
    if not cpus:
        print("No CPUs found in cpus.mk")
        return

    # Create output buffer
    memory = bytearray(DEFAULT_SIZE)

    print("Merging CPUs into unified memory image...")
    for cpu in cpus:
        name = cpu["name"]
        offset = cpu["offset"]
        bin_path = cpu["bin"]

        if not bin_path.exists():
            print(f"  [WARN] {bin_path} not found. Skipping {name}")
            continue

        with open(bin_path, "rb") as f:
            data = f.read()

        end = offset + len(data)
        if end > len(memory):
            print(f"  [ERROR] {name} at offset 0x{offset:x} exceeds memory size!")
            continue

        memory[offset:end] = data
        print(f"  [{name:8s}] 0x{offset:08x} ~ 0x{end:08x}  ({len(data)} bytes)")

    with open(OUTPUT_FILE, "wb") as f:
        f.write(memory)

    print(f"\nUnified memory image created: {OUTPUT_FILE}")
    print(f"Total size: {len(memory)} bytes (0x{len(memory):x})")

if __name__ == "__main__":
    main()