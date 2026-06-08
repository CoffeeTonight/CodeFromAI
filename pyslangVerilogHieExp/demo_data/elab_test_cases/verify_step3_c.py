#!/usr/bin/env python3
"""
C verification driver (parameter passing 중첩):
- Load step3_nested_param_passing.v (nested for + outer params + genvar expressions in overrides)
- Call unroll with module parameters
- Assert exact hierarchy + FULLY RESOLVED numeric parameter values (the C goal)
- Run DQL-style checks

Run: python demo_data/elab_test_cases/verify_step3_c.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.generate_unroller import unroll_generate_in_body

def simple_name_query(q: str, instances: list) -> list:
    import re
    m = re.search(r'name\s*~\s*"([^"]+)"', q)
    if not m:
        return []
    pat = m.group(1)
    # Escape regex specials (esp [ ] from generate indices) then turn * into .*
    escaped = re.escape(pat).replace(r'\*', '.*')
    rx = re.compile(escaped)
    return [inst for inst in instances if rx.search(inst.get("name", ""))]

def main():
    print("=" * 72)
    print("C VERIFICATION: Nested generate + parameter passing (expressions with multiple genvars + outer params)")
    print("=" * 72)

    rtl_path = Path(__file__).parent / "step3_nested_param_passing.v"
    qpath = Path(__file__).parent / "step3_queries.txt"

    src = rtl_path.read_text(encoding="utf-8")

    # === Critical C call ===
    # Both NUM_CLUSTERS and CORES_PER_CLUSTER must propagate into the nested loops
    # and expressions like c * CORES_PER_CLUSTER + i and TOTAL must fully resolve.
    params = {"NUM_CLUSTERS": 2, "CORES_PER_CLUSTER": 2}
    unrolled = unroll_generate_in_body(src, params)

    print(f"\nUnroller produced {len(unrolled)} instances")
    for r in unrolled:
        print(f"  {r.get('inst_name'):40}  module={r.get('module'):12}  params={r.get('parameters', {})}")

    all_inst = []
    for r in unrolled:
        all_inst.append({
            "name": "top.step3." + r["inst_name"],
            "module": r.get("module", ""),
            "parameters": r.get("parameters", {}),
            "file": str(rtl_path),
        })

    # Expected for NUM_CLUSTERS=2, CORES_PER_CLUSTER=2:
    #   top.step3.u_cluster[0].u_core[0].u_leaf   .CLUSTER_ID=0, .CORE_ID=0, .TOTAL_CORES=4
    #   ...[0].u_core[1]...                        .CLUSTER_ID=0, .CORE_ID=1, .TOTAL_CORES=4
    #   ...[1].u_core[0]...                        .CLUSTER_ID=1, .CORE_ID=2, .TOTAL_CORES=4
    #   ...[1].u_core[1]...                        .CLUSTER_ID=1, .CORE_ID=3, .TOTAL_CORES=4

    names = [x["name"] for x in all_inst]
    total = len(all_inst)
    has_all_indices = all(any(f"u_cluster[{c}].u_core[{i}]" in n for n in names) for c in (0,1) for i in (0,1))

    # Check resolved params (the real C requirement)
    resolved_ok = True
    for inst in all_inst:
        p = inst["parameters"]
        if ".CORE_ID" not in p or not p[".CORE_ID"].isdigit():
            resolved_ok = False
        if ".TOTAL_CORES" not in p or p[".TOTAL_CORES"] != "4":
            resolved_ok = False

    print(f"\n--- Structural + Resolved Param Check ---")
    print(f"  total instances          : {total} (want 4)")
    print(f"  all nested indices present : {has_all_indices}")
    print(f"  all param values numeric + TOTAL_CORES=4 : {resolved_ok}")

    struct_ok = (total == 4 and has_all_indices and resolved_ok)

    if not struct_ok:
        print("\n*** C STRUCTURAL/PARAM FAIL - unroller still needs work for nested param passing ***")
        return 2

    # DQL (simple matcher)
    queries = []
    for line in qpath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            queries.append(line)

    print(f"\n--- DQL checks ({len(queries)} queries) ---")
    all_pass = True
    for q in queries:
        hits = simple_name_query(q, all_inst)
        print(f"  [{len(hits):2}] {q}")

    # Hard C requirements
    specific = [
        ('name ~ "*u_leaf*"', 4),
        ('name ~ "*u_cluster[0].u_core[0]*"', 1),
        ('name ~ "*u_cluster[1].u_core[1]*"', 1),
    ]
    print("\n--- Targeted C Verification (resolved hierarchy) ---")
    for q, want in specific:
        hits = simple_name_query(q, all_inst)
        got = len(hits)
        status = "PASS" if got == want else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {q}  -> {got} (want {want})")

    # Extra: verify one resolved param value directly from the data
    print("\n--- Direct param value spot checks (C core) ---")
    for inst in all_inst:
        if "u_cluster[0].u_core[1]" in inst["name"]:
            cid = inst["parameters"].get(".CORE_ID")
            tot = inst["parameters"].get(".TOTAL_CORES")
            print(f"  cluster0.core1 CORE_ID={cid} TOTAL={tot}")
            if cid != "1" or tot != "4":
                all_pass = False

    print("\n" + "=" * 72)
    if struct_ok and all_pass:
        print("*** C SUCCESS: nested generate + full parameter expression resolution working ***")
        rc = 0
    else:
        print("*** C NOT YET COMPLETE ***")
        rc = 1
    print("=" * 72)
    return rc


if __name__ == "__main__":
    sys.exit(main())