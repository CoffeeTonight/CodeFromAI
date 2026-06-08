#!/usr/bin/env python3
"""
Large-scale SoC performance & correctness test for the block-tree generate unroller.

Generates a synthetic SoC with heavy generate usage and measures:
- Parsing + unrolling time (pure generalized/block-tree path preferred)
- Total instances discovered
- Rough hierarchy depth
- Sample deep paths (to verify label/genvar correctness)
"""

import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.generate_unroller import GenerateUnroller, unroll_generate_in_body

# Powerful parallelism for multi-module SoC
PARALLEL_SOC_WORKERS = max(1, (os.cpu_count() or 4) - 1)


def _unroll_one_module(path: Path, params: dict):
    """Module-level function so it is picklable for ProcessPoolExecutor."""
    if path.exists():
        with open(path) as f:
            src = f.read()
        return unroll_generate_in_body(src, params)
    return []

RTL_DIR = Path(__file__).parent / "rtl"
TOP_FILE = RTL_DIR / "soc_top.v"

def main():
    print("=" * 70)
    print("LARGE SYNTHETIC SoC TEST (~1000 instances, depth up to 10)")
    print("=" * 70)

    if not TOP_FILE.exists():
        print("ERROR: soc_top.v not found. Run generate_large_soc.py first.")
        return 1

    print(f"Top file: {TOP_FILE}")

    # Large parameters to push toward 1000+ instances
    params = {
        "NUM_CPU_CLUSTERS": 8,
        "NUM_PERIPH_SUBSYS": 4,
        "MAX_DEPTH": 10,
    }

    print(f"Parameters: {params}")

    with open(TOP_FILE) as f:
        src = f.read()

    u = GenerateUnroller()

    # Prefer the new block-tree path (disable deep special for pure test)
    # We still keep the old safety nets for comparison, but measure the new path
    start = time.time()
    insts = u.unroll_generate_blocks(src, params)
    elapsed = time.time() - start

    print(f"\nUnroll time (block-tree preferred path): {elapsed:.3f} s")
    print(f"Total instances discovered: {len(insts)}")

    # POWERFUL PARALLELISM: unroll heavy generated modules in parallel using processes
    # This is the "파워풀한거" applied at SoC scale - independent modules across cores.
    heavy = ["riscv_core.v", "axi_crossbar.v", "arm_cortex_stub.v", "ahb_to_apb_bridge.v", "uart.v", "spi_master.v"]
    t2 = time.time()
    extra_insts = 0

    with ProcessPoolExecutor(max_workers=PARALLEL_SOC_WORKERS) as pool:
        futures = {pool.submit(_unroll_one_module, RTL_DIR / h, params): h for h in heavy}
        for fut in as_completed(futures):
            try:
                res = fut.result()
                extra_insts += len(res)
            except Exception as e:
                print(f"  Parallel module failed: {futures[fut]} - {e}")

    t_heavy = time.time() - t2
    print(f"Heavy IP unroll time (parallel {PARALLEL_SOC_WORKERS} workers): {t_heavy:.3f} s, total extra insts: {extra_insts}")

    # Rough depth estimation from instance names
    max_depth = 0
    for inst in insts:
        depth = inst["inst_name"].count(".")
        if depth > max_depth:
            max_depth = depth

    print(f"Approximate max hierarchy depth observed: {max_depth}")

    # Sample some deep paths
    print("\nSample deep paths (first 5 with depth >= 4):")
    deep = [i for i in insts if i["inst_name"].count(".") >= 4][:5]
    for d in deep:
        print(f"  {d['inst_name']}")
        if d.get("parameters"):
            print(f"    params: {d['parameters']}")

    # Check for presence of key IP types
    has_riscv = any("riscv_core" in i["module"].lower() for i in insts)
    has_uart  = any("uart" in i["module"].lower() for i in insts)
    has_i3c   = any("i3c" in i["module"].lower() for i in insts)
    has_dma   = any("dma" in i["module"].lower() for i in insts)
    has_pcie  = any("pcie" in i["module"].lower() for i in insts)

    print(f"\nIP presence check:")
    print(f"  RISC-V cores: {has_riscv}")
    print(f"  UARTs:        {has_uart}")
    print(f"  I3C masters:  {has_i3c}")
    print(f"  DMA engines:  {has_dma}")
    print(f"  PCIe RC:      {has_pcie}")

    print("\n" + "=" * 70)
    print("Large SoC test completed.")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    sys.exit(main())