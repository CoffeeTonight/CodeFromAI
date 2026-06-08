#!/usr/bin/env python3
"""
Batch evaluation script for Generate + DQL integration.

This script:
- Unrolls generate-for from our test cases
- Runs multiple DQL queries on the result
- Reports pass/fail in non-interactive mode
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.generate_unroller import unroll_generate_in_body
from tools.dql_query import query_dql, load_instances

def main():
    print("=" * 70)
    print("BATCH EVALUATION: Generate-for + DQL Search")
    print("=" * 70)

    # 1. Build instances from generate
    all_inst = []

    # cpu
    with open("tests/generate_for/cpu_cluster.v") as f:
        res = unroll_generate_in_body(f.read(), {"NUM_CORES": 4})
    for r in res:
        all_inst.append({
            "name": "top.u_cpu_cluster." + r["inst_name"],
            "module": r["module"],
            "params": r.get("parameters", {}),
            "filepath": "tests/generate_for/cpu_cluster.v"
        })

    # mem
    with open("tests/generate_for/memory_bank.v") as f:
        res = unroll_generate_in_body(f.read(), {"BANKS": 8})
    for r in res:
        all_inst.append({
            "name": "top.u_mem." + r["inst_name"],
            "module": r["module"],
            "params": r.get("parameters", {}),
            "filepath": "tests/generate_for/memory_bank.v"
        })

    # stress mixed generate (for + if + case) - CRITICAL 100-iter target
    with open("tests/generate_for/stress_generate.v") as f:
        res = unroll_generate_in_body(f.read(), {"DEPTH": 3, "WIDTH": 8})
    for r in res:
        all_inst.append({
            "name": "top.u_stress." + r["inst_name"],
            "module": r["module"],
            "params": r.get("parameters", {}),
            "filepath": "tests/generate_for/stress_generate.v"
        })

    # Write temp data
    tmp = Path("/tmp/generate_batch_instances.json")
    tmp.write_text(json.dumps(all_inst, indent=2))

    # Monkey patch for this run
    import tools.dql_query as dq
    original = dq.load_instances
    dq.load_instances = lambda p=None: json.loads(tmp.read_text())

    print(f"\nTotal generate-unrolled instances: {len(all_inst)}")

    # 2. Run batch queries and evaluate
    test_cases = [
        ("module ~ \"sram\"", 8, "Should find 8 sram instances"),
        ("name ~ \"*u_core[0]*\"", 1, "Should find exactly one u_core[0]"),
        ("name ~ \"*bank[3]*\"", 1, "Should find bank[3]"),
        ("name ~ \"*u_core[2]*\"", 1, "u_core[2] from cluster"),
        # stress mixed generate (updated after perf overhaul + structural priority)
        ("name ~ \"*u_stress*\"", 35, "stress_generate: 35 (structural + narrow boosters now fully elaborate mixed for/if/case arms + hierarchy)"),
        ("name ~ \"*depth[0].even*\"", 8, "stress: even d=0 lane* (WIDTH=8)"),
        ("name ~ \"*depth[1].odd*\"", 8, "stress: odd d=1 lane_odd*"),
        ("name ~ \"*m0.u0*\"", 6, "stress: case arm 0 (w%3==0) across 2 even ds * 3 lanes = 6"),
    ]

    passed = 0
    failed = 0

    print("\n--- Query Results ---")
    for query, expected_count, desc in test_cases:
        res = query_dql(query)
        actual = len(res)
        status = "PASS" if actual == expected_count else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {query}")
        print(f"        Expected: {expected_count}, Got: {actual}  -- {desc}")
        if status == "FAIL" and res:
            print(f"        First result: {res[0]['name']}")

    print("\n" + "=" * 70)
    print(f"FINAL BATCH RESULT: {passed} passed, {failed} failed")
    if failed == 0:
        print("*** ALL GENERATE + DQL BATCH TESTS PASSED ***")
    else:
        print("*** SOME TESTS FAILED - NEEDS FURTHER WORK ***")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
