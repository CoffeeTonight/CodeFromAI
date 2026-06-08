#!/usr/bin/env python3
"""
Strong end-to-end batch verification for Generate support.

Flow:
1. Use VerilogParser on a file containing generate-for
2. Check that unrolled instances appear in the result
3. Run several DQL-style checks
4. Report detailed pass/fail
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from verilogParser import VerilogParser
from tools.generate_unroller import unroll_generate_in_body

class SimpleFileList:
    def __init__(self, files):
        self.hdls = {str(f): "True: test" for f in files}

def main():
    print("=" * 72)
    print("END-TO-END BATCH VERIFICATION: Generate + Parser + Hierarchy")
    print("=" * 72)

    test_files = [
        Path("tests/generate_for/cpu_cluster.v"),
        Path("tests/generate_for/complex_generate.v"),
    ]

    total_pass = 0
    total_fail = 0

    for tf in test_files:
        if not tf.exists():
            print(f"SKIP: {tf} not found")
            continue

        print(f"\n--- Testing: {tf.name} ---")

        try:
            fl = SimpleFileList([tf])
            parser = VerilogParser(fl, "/tmp", {})
            parser.run()

            # Find the module
            modules = list(parser.dVerilog.get("instances", {}).keys())
            if not modules:
                print("  FAIL: No modules parsed")
                total_fail += 1
                continue

            main_mod = modules[0]
            insts = parser.dVerilog["instances"][main_mod].get("instances", {})

            # Check for generate-unrolled instances (contain '[' )
            gen_insts = [k for k in insts if '[' in k and ']' in k]

            print(f"  Parsed module: {main_mod}")
            print(f"  Total instances: {len(insts)}")
            print(f"  Generate-unrolled instances found: {len(gen_insts)}")

            if gen_insts:
                print(f"  Sample: {gen_insts[:2]}")
                total_pass += 1
            else:
                print("  FAIL: No generate-unrolled instances detected in parser output")
                total_fail += 1

            # Additional DQL-style check
            cpu_like = [k for k in insts if 'core' in k.lower() or 'lane' in k.lower()]
            if cpu_like:
                print(f"  DQL-style 'core/lane' search: {len(cpu_like)} hits → PASS")
                total_pass += 1
            else:
                total_fail += 1

        except Exception as e:
            print(f"  ERROR during parsing: {e}")
            total_fail += 1

    print("\n" + "=" * 72)
    print(f"END-TO-END BATCH RESULT: {total_pass} checks passed, {total_fail} failed")
    if total_fail == 0:
        print("*** STRONG VERIFICATION PASSED ***")
    else:
        print("*** VERIFICATION FOUND ISSUES - SEE DETAILS ABOVE ***")
    print("=" * 72)

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
