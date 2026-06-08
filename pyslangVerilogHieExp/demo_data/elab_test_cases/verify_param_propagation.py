#!/usr/bin/env python3
"""
verify_param_propagation.py

Verification for inter-module parameter propagation (the major next target).

Scenario:
- Parent module has PARENT_WIDTH
- Parent instantiates param_child with overrides that use parent's parameter
  (e.g. .CHILD_WIDTH(PARENT_WIDTH / 4))
- Child uses CHILD_WIDTH inside its generate-for to create instances
- We must see the child's generated instances with parameters correctly resolved
  from the value passed by the parent.

This tests the new ParameterPropagator.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.parameter_propagator import ParameterPropagator


def main():
    print("=" * 72)
    print("PARAMETER PROPAGATION VERIFICATION (Inter-module param passing)")
    print("=" * 72)

    base = Path(__file__).parent / "param_propagation"

    parent_src = (base / "parent.v").read_text(encoding="utf-8")
    child_src  = (base / "child.v").read_text(encoding="utf-8")
    leaf_src   = (base / "leaf.v").read_text(encoding="utf-8")

    prop = ParameterPropagator()
    prop.register_module("param_propagation_parent", parent_src)
    prop.register_module("param_child", child_src)
    prop.register_module("leaf_unit", leaf_src)

    # Elaborate with a specific top-level parameter value
    results = prop.elaborate(
        top_name="param_propagation_parent",
        top_params={"PARENT_WIDTH": 16}
    )

    print(f"\nElaborated {len(results)} instances\n")
    for r in results:
        print(f"  {r['name']:55}  module={r['module']:20}  params={r.get('parameters', {})}")

    # === Verification targets ===
    # We expect child instances whose parameters reflect the parent's value:
    # u_child_direct     -> CHILD_WIDTH = 16/4 = 4,  CHILD_DEPTH=16
    # u_child_computed   -> CHILD_WIDTH = 16/2 = 8,  CHILD_DEPTH=12

    # Check that we have generated lanes from both children with correct resolved values
    direct_lanes = [r for r in results if "u_child_direct" in r["name"] and "u_lane" in r["name"]]
    computed_lanes = [r for r in results if "u_child_computed" in r["name"] and "u_lane" in r["name"]]

    print(f"\n--- Checks ---")
    print(f"  Direct child lanes found     : {len(direct_lanes)} (want 4)")
    print(f"  Computed child lanes found   : {len(computed_lanes)} (want 8)")

    passed = True

    # The key success for inter-module param propagation:
    # The number of generated items in the child is driven by the value passed from the parent.
    if len(direct_lanes) != 4:
        print("    FAIL: direct child lane count wrong")
        passed = False
    if len(computed_lanes) != 8:
        print("    FAIL: computed child (passed WIDTH=8) lane count wrong — propagation failed")
        passed = False

    # Verify that leaf instances received the propagated DEPTH value from the parent through the child
    leafs = [r for r in results if r["module"] == "leaf_unit"]
    print(f"  Leaf instances total         : {len(leafs)}")

    # Check a leaf from the computed path has the correct DEPTH coming from parent
    for leaf in leafs:
        if "u_child_computed" in leaf["name"]:
            if leaf["parameters"].get(".DEPTH") != "12":
                print("    FAIL: DEPTH not correctly propagated to leaf in computed child")
                passed = False
            break

    if passed:
        print("\n*** PARAMETER PROPAGATION VERIFICATION PASSED ***")
        print("    (Parent param → child override with expression → child's generate loop count + leaf params all correct)")
        return 0
    else:
        print("\n*** PARAMETER PROPAGATION VERIFICATION FAILED ***")
        return 1


if __name__ == "__main__":
    sys.exit(main())
