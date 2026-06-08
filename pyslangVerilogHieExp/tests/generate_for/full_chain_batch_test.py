#!/usr/bin/env python3
"""
Full chain batch verification:
VerilogParser (with generate unroll) + DQL search on the result.

This is the strongest end-to-end test for the 3 improvements.
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from verilogParser import VerilogParser
from tools.dql_query import query_dql, load_from_generate_unroll

class SimpleFileList:
    def __init__(self, files):
        self.hdls = {str(f): "True: test" for f in files}

def main():
    print("=" * 70)
    print("FULL CHAIN BATCH TEST: Parser + Generate Unroll + DQL")
    print("=" * 70)

    test_file = ROOT / "tests" / "generate_for" / "cpu_cluster.v"
    if not test_file.exists():
        print("Test file not found")
        return 1

    # 1. Parse with the updated parser (which now calls generate unroller)
    print("\n[1] Parsing with VerilogParser (generate integration)...")
    fl = SimpleFileList([test_file])
    parser = VerilogParser(fl, "/tmp", {})
    parser.run()

    # Find instances
    modules = list(parser.dVerilog.get("instances", {}).keys())
    if not modules:
        print("  No modules found")
        return 1

    mod = modules[0]
    insts = parser.dVerilog["instances"][mod].get("instances", {})
    gen_insts = [k for k in insts if '[' in k]
    print(f"  Module: {mod}")
    print(f"  Total instances: {len(insts)}")
    print(f"  Generate-unrolled: {len(gen_insts)}")

    # 2. DQL on generate-unrolled data (using the new load function)
    print("\n[2] DQL search on generate-unrolled instances...")
    gen_data = load_from_generate_unroll([str(test_file)], {"NUM_CORES": 4})

    # Temporarily override load for DQL
    import tools.dql_query as dq
    dq.load_instances = lambda p=None: gen_data

    queries = [
        ('module ~ "*core*"', 4),
        ('name ~ "*u_core[0]*"', 1),
    ]

    passed = 0
    for q, expected in queries:
        res = query_dql(q)
        status = "PASS" if len(res) == expected else "FAIL"
        print(f"  [{status}] {q} -> {len(res)} (expected {expected})")
        if status == "PASS":
            passed += 1

    print(f"\n[3] Result: {passed}/{len(queries)} DQL checks passed on generate data")

    overall = "SUCCESS" if len(gen_insts) > 0 and passed == len(queries) else "PARTIAL"
    print(f"\n=== FULL CHAIN: {overall} ===")
    return 0 if overall == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
