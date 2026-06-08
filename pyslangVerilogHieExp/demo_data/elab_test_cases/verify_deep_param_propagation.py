#!/usr/bin/env python3
"""
Deep (5+ level) parameter propagation verification with complex expressions.

Tests:
- 5+ levels of module instantiation with parameter passing
- Complex arithmetic expressions including nested parentheses, *, /, +, -, %
- The final generated instance count and parameter values at the leaf
  must match the fully reduced result after all levels of computation.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.parameter_propagator import ParameterPropagator

def main():
    print("=" * 80)
    print("DEEP 5+ LEVEL PARAMETER PROPAGATION + COMPLEX EXPRESSIONS TEST")
    print("=" * 80)

    chain_path = Path(__file__).parent / "deep_param_propagation" / "chain.v"
    src = chain_path.read_text(encoding="utf-8")

    prop = ParameterPropagator()
    # Register all modules from the chain file
    prop.register_module("level5_top", src)
    prop.register_module("level4", src)
    prop.register_module("level3", src)
    prop.register_module("level2", src)
    prop.register_module("level1", src)
    prop.register_module("level0", src)

    # Use a non-trivial top value
    TOP_VAL = 64
    results = prop.elaborate("level5_top", {"TOP_VAL": TOP_VAL})

    print(f"\nTop parameter: TOP_VAL = {TOP_VAL}")
    print(f"Total elaborated instances: {len(results)}")

    # Filter leaf level0 instances
    leaves = [r for r in results if r["module"] == "level0"]
    print(f"Level0 (leaf) instances: {len(leaves)}")

    # Expected calculation (must match the expressions in chain.v):
    # L4 = ((64/2)+8)*3 - (64%7) = 119
    # L3 = (119/4) + (119%5) -1 = 32
    # L2 = ((32+7)*2)/3 = 26
    # L1 = (26*3) + (26%2) = 78
    # → 78 level0 instances
    expected_l1_val = 78
    expected_leaf_count = expected_l1_val

    print(f"\nExpected leaf count (after full expression reduction): {expected_leaf_count}")
    print(f"Actual leaf count: {len(leaves)}")

    if len(leaves) != expected_leaf_count:
        print("*** FAIL: Leaf count does not match expected propagated value ***")
        return 1

    # Check a few leaf parameter values to verify deep expression evaluation
    # level0 FINAL_VAL = L1_VAL * 2 + i   (L1_VAL ended up as 78)
    # For i=0 → 156, i=5 → 161, i=77 → 233
    sample_checks = [
        (0, 156),
        (5, 161),
        (77, 233),
    ]

    passed = True
    for idx, expected_final in sample_checks:
        # Look for any leaf that has the index in its hierarchical name
        matching = [l for l in leaves if f"[{idx}]" in l["name"]]
        if matching:
            actual = matching[0]["parameters"].get(".FINAL_VAL")
            print(f"  Leaf containing [{idx}]: FINAL_VAL={actual} (expected {expected_final})")
            if str(actual) != str(expected_final):
                print(f"    *** MISMATCH ***")
                passed = False
        else:
            print(f"  Could not find any leaf containing index [{idx}]")
            passed = False

    # Also verify that the deepest expressions produced correct intermediate values
    # by checking one of the level1 instances (if present in results)
    level1_insts = [r for r in results if r["module"] == "level1"]
    if level1_insts:
        print(f"\n  Sample Level1 instance params: {level1_insts[0]['parameters']}")

    print("\n" + "=" * 80)
    if passed and len(leaves) == expected_leaf_count:
        print("*** DEEP 5+ LEVEL + COMPLEX EXPRESSION PROPAGATION VERIFICATION PASSED ***")
        print("    Parameters correctly flowed and were computed through 5+ module levels")
        print("    with nested parentheses and multiple arithmetic operators.")
        return 0
    else:
        print("*** VERIFICATION FAILED ***")
        return 1


if __name__ == "__main__":
    sys.exit(main())
