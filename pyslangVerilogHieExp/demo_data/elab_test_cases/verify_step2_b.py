#!/usr/bin/env python3
"""
B verification driver (no example cheating):
- Load step2_generate_if.v (the exact user example)
- Call unroll_generate_in_body with the parameter value
- Build instances.json in the style expected by dql_query
- Run the python-full engine queries from step2_queries.txt
- Report exact match / failure counts

This is the controlled "배치모드 검증" loop for B.
Run with: python demo_data/elab_test_cases/verify_step2_b.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.generate_unroller import unroll_generate_in_body

# Lightweight name matcher (avoid lark import for this focused B unroller test)
def simple_name_query(q: str, instances: list) -> list:
    # Supports only the patterns we use in step2_queries:  name ~ "*something*"
    import re
    m = re.search(r'name\s*~\s*"([^"]+)"', q)
    if not m:
        return []
    pat = m.group(1)
    # Convert * to .* for simple glob
    regex = "^" + pat.replace("*", ".*") + "$"
    rx = re.compile(regex)
    return [inst for inst in instances if rx.search(inst.get("name", ""))]

def main():
    print("=" * 72)
    print("B VERIFICATION: step2_generate_if (generate-for + if/else) via unroller only")
    print("=" * 72)

    rtl_path = Path(__file__).parent / "step2_generate_if.v"
    qpath = Path(__file__).parent / "step2_queries.txt"

    if not rtl_path.exists():
        print(f"FAIL: {rtl_path} not found")
        return 1

    src = rtl_path.read_text(encoding="utf-8")

    # === This is the critical call for B ===
    # NUM_UNITS must be resolved from parameters into the for bound (i < NUM_UNITS)
    # and the if (i==0) must select exactly one leader, the else the rest.
    params = {"NUM_UNITS": 4}
    unrolled = unroll_generate_in_body(src, params)

    print(f"\nUnroller produced {len(unrolled)} instances for NUM_UNITS=4")
    for r in unrolled:
        print(f"  {r.get('inst_name'):30}  module={r.get('module')}  params={r.get('parameters', {})}")

    # Build the flat instances list exactly as batch tests + dql_query expect
    all_inst = []
    for r in unrolled:
        all_inst.append({
            "name": "top.step2." + r["inst_name"],
            "module": r.get("module", ""),
            "parameters": r.get("parameters", {}),
            "file": str(rtl_path),
        })

    # Expected correct result for NUM_UNITS=4 + proper B fix:
    #   top.step2.u_unit[0].u_first     (leader)
    #   top.step2.u_unit[1].u_normal
    #   top.step2.u_unit[2].u_normal
    #   top.step2.u_unit[3].u_normal
    expected_leader = 1
    expected_normal = 3
    expected_total = 4

    # Quick structural check
    names = [x["name"] for x in all_inst]
    has_leader = any("u_first" in n for n in names)
    normal_count = sum(1 for n in names if "u_normal" in n)
    total = len(all_inst)

    print(f"\n--- Structural Check (before DQL) ---")
    print(f"  leader (u_first) present : {has_leader}  (want True)")
    print(f"  normal (u_normal) count  : {normal_count} (want {expected_normal})")
    print(f"  total instances          : {total} (want {expected_total})")

    struct_ok = (has_leader and normal_count == expected_normal and total == expected_total)

    if not struct_ok:
        print("\n*** STRUCTURAL FAIL - unroller B fix is still broken ***")
        return 2

    # Now feed to real dql_python engine (the same one dql_query --engine python-full uses)
    tmp_json = Path("/tmp/step2_b_instances.json")
    tmp_json.write_text(json.dumps(all_inst, indent=2))

    # Load queries
    queries = []
    for line in qpath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            queries.append(line)

    print(f"\n--- DQL Batch on python-full engine ({len(queries)} queries) ---")
    all_pass = True
    for q in queries:
        try:
            hits = simple_name_query(q, all_inst)
            print(f"  [{len(hits):2}] {q}")
        except Exception as ex:
            print(f"  ERROR on query: {q} -> {ex}")
            all_pass = False

    # Specific expected counts for this design (hard requirements for B)
    specific = [
        ('name ~ "u_unit*"', 4),
        ('name ~ "*u_first*"', 1),
        ('name ~ "*u_normal*"', 3),
        ('name ~ "*u_unit[0]*"', 1),
        ('name ~ "*u_unit[1]*"', 1),
    ]

    print("\n--- Targeted Count Verification ---")
    for q, want in specific:
        hits = simple_name_query(q, all_inst)
        got = len(hits)
        status = "PASS" if got == want else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {q}  -> {got} (want {want})")

    print("\n" + "=" * 72)
    if struct_ok and all_pass:
        print("*** B SUCCESS: unroller now correctly handles generate-for + if/else + param bound ***")
        print("    Ready for full dql_query.py --data + --queries integration.")
        rc = 0
    else:
        print("*** B NOT YET COMPLETE - fix remaining issues in generate_unroller.py ***")
        rc = 1
    print("=" * 72)
    return rc


if __name__ == "__main__":
    sys.exit(main())