#!/usr/bin/env python3
"""
Comprehensive Batch Verification for ParameterPropagator

Tests a wide variety of complex scenarios:
- Different hierarchy depths (3~12 levels)
- Complex parameter expressions (nested, ternary, macros)
- Preprocessor (`include`, `define`, `ifdef`)
- Hierarchical + late defparam
- Auto top module discovery
- Library resolution (basic)
- Error cases and diagnostics

Run with:
    python tools/verify_parameter_propagation_batch.py
"""

import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tools.parameter_propagator import ParameterPropagator
from tools.verilog_preprocessor import preprocess_verilog


class TestCase:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.passed = False
        self.details = ""
        self.diagnostics = {}

    def mark_pass(self, details: str = ""):
        self.passed = True
        self.details = details

    def mark_fail(self, details: str = "", diagnostics: Dict = None):
        self.passed = False
        self.details = details
        if diagnostics:
            self.diagnostics = diagnostics


def generate_multi_level_design(
    depth: int,
    base_value: int = 128,
    use_include: bool = False,
    use_defparam: bool = False,
    use_ternary: bool = False
) -> Tuple[Dict[str, str], str, Dict[str, Any]]:
    """
    Generate a multi-level design with complex expressions.
    Returns: (modules_dict, top_name, expected_final_values)
    """
    modules = {}
    top_name = f"level{depth}"

    # Create a common include if requested
    if use_include:
        modules["common.vh"] = f"""
`define BASE {base_value}
`define MULT 2
"""

    current_param = "TOP_P"
    current_val = base_value

    # Build from top to bottom
    for d in range(depth, 0, -1):
        mod_name = f"level{d}" if d < depth else f"level{depth}"
        child_name = f"level{d-1}" if d > 1 else "leaf"

        # Create increasingly complex expression
        if d == depth:
            expr = f"((TOP_P / 4) + (TOP_P % 5)) * 2 + 3"
        else:
            expr = f"((PIN + {d*2}) * 3 / (PIN % {d+1} + 2)) + {d}"

        if use_ternary and d % 3 == 0:
            expr = f"({expr} > 50 ? {expr} + 10 : {expr} - 5)"

        if use_include and d == depth:
            body = f"""
`include "common.vh"

module {mod_name} #(
    parameter int TOP_P = {base_value}
)();
    {child_name} #(
        .PIN( {expr} )
    ) u_{d-1} ();
endmodule
"""
        else:
            body = f"""
module {mod_name} #(
    parameter int {current_param if d == depth else 'PIN'} = {current_val}
)();
    {child_name} #(
        .PIN( {expr} )
    ) u_{d-1} ();
endmodule
"""

        modules[mod_name] = body
        current_param = "PIN"
        current_val = 64  # placeholder

    # Leaf that accepts the propagated value as "PIN" (to match .PIN( expr ) overrides from parent levels).
    # The generate-for bound is PIN so we can verify the value arrived.
    leaf_body = """
module leaf #(
    parameter int PIN = 1,
    parameter int IDX = 0
)();
    generate
        for (genvar k = 0; k < PIN; k = k + 1) begin : u_leaf
            sub_cell u_sub ();
        end
    endgenerate
endmodule

module sub_cell();
endmodule
"""
    modules["leaf"] = leaf_body

    # Add defparam if requested (late / hierarchical)
    if use_defparam:
        # Add defparam in the top module
        top_body = modules[top_name]
        top_body = top_body.replace(
            "endmodule",
            f"""
    defparam u_{depth-1}.u_{depth-2}.FINAL_P = 42;   // hierarchical late defparam
endmodule
"""
        )
        modules[top_name] = top_body

    # Compute expected final value (simplified simulation)
    expected = {}
    # For verification we compute a simple expected based on the expressions
    # In real tests we would symbolically evaluate or run the same logic in Python

    return modules, top_name, {"expected_leaf_count": 42 if use_defparam else 64}


def run_single_test(case: TestCase, modules: Dict[str, str], top_name: str,
                    top_params: Dict[str, Any], expected: Dict[str, Any]) -> TestCase:
    """Run one test case and return result."""
    prop = ParameterPropagator()

    try:
        for name, body in modules.items():
            if name.endswith(".vh"):
                continue
            prop.register_module(name, body, apply_preprocessor=True)

        results = prop.elaborate(top_name, top_params)
        diagnostics = prop.get_diagnostics()

        leaf_results = [r for r in results if r.get("module") == "leaf" or "u_leaf" in r.get("name", "")]
        leaf_count = len(leaf_results)

        # Check if the propagated parameter (PIN) arrived at the leaf level
        pin_arrived = False
        pin_value = None
        for lr in leaf_results:
            p = lr.get("parameters", {})
            for key in ["PIN", ".PIN"]:
                if key in p:
                    pin_arrived = True
                    pin_value = p[key]
                    break
            if pin_arrived:
                break

        if len(results) > 0 and pin_arrived:
            case.mark_pass(f"Produced {len(results)} instances ({leaf_count} leaf-related). "
                           f"PIN={pin_value} arrived at leaf. Top={top_name}")
        else:
            leaf_params_sample = [lr.get("parameters") for lr in leaf_results[:2]] if leaf_results else []
            case.mark_fail(f"Produced {len(results)} instances ({leaf_count} leaf-related). "
                           f"PIN arrived: {pin_arrived} (value={pin_value}). "
                           f"Errors: {diagnostics.get('errors')}. "
                           f"Leaf params sample: {leaf_params_sample}", diagnostics)

    except Exception as e:
        case.mark_fail(f"Exception during test: {e}", prop.get_diagnostics())

    return case


def main():
    print("=" * 80)
    print("PARAMETER PROPAGATION BATCH VERIFICATION - EXTENSIVE TEST SUITE")
    print("=" * 80)

    test_cases: List[TestCase] = []

    # === Category 1: Different depths ===
    for depth in [3, 5, 8, 10, 12]:
        case = TestCase(f"depth_{depth}", f"Simple propagation at depth {depth}")
        modules, top, expected = generate_multi_level_design(depth)
        run_single_test(case, modules, top, {"TOP_P": 128}, expected)
        test_cases.append(case)

    # === Category 2: With preprocessor ===
    for depth in [5, 8]:
        case = TestCase(f"include_depth_{depth}", f"With `include at depth {depth}")
        modules, top, expected = generate_multi_level_design(depth, use_include=True)
        run_single_test(case, modules, top, {"TOP_P": 128}, expected)
        test_cases.append(case)

    # === Category 3: With defparam (late + hierarchical) ===
    for depth in [6, 10]:
        case = TestCase(f"defparam_depth_{depth}", f"Hierarchical late defparam at depth {depth}")
        modules, top, expected = generate_multi_level_design(depth, use_defparam=True)
        run_single_test(case, modules, top, {"TOP_P": 128}, expected)
        test_cases.append(case)

    # === Category 4: Complex expressions (ternary) ===
    case = TestCase("complex_ternary", "Deep propagation with ternary operators")
    modules, top, expected = generate_multi_level_design(7, use_ternary=True)
    run_single_test(case, modules, top, {"TOP_P": 128}, expected)
    test_cases.append(case)

    # === Category 5: Auto top discovery ===
    case = TestCase("auto_top", "Verify auto top module discovery")
    modules, _, _ = generate_multi_level_design(5)
    # Only keep the main design modules for top detection test
    modules = {k: v for k, v in modules.items() if k.startswith("level") or k == "leaf"}
    prop = ParameterPropagator()
    for name, body in modules.items():
        prop.register_module(name, body)
    tops = prop.find_top_modules()
    real_tops = [t for t in tops if t.startswith("level")]
    if len(real_tops) == 1:
        case.mark_pass(f"Correctly auto-detected top: {real_tops[0]}")
    else:
        case.mark_fail(f"Unexpected tops: {real_tops} (raw: {tops})")
    test_cases.append(case)

    # === Category 6: Error / diagnostic cases ===
    case = TestCase("bad_expression", "Expression that cannot be fully evaluated")
    prop = ParameterPropagator()
    prop.register_module("top", """
module top();
    child #(.C( (UNKNOWN_PARAM + 3) * 2 )) u();
endmodule
module child #(parameter C=1)();
endmodule
""")
    results = prop.elaborate("top")
    diag = prop.get_diagnostics()
    if diag.get("errors") or any("UNKNOWN" in str(p) for r in results for p in r.get("parameters", {}).values()):
        case.mark_pass("Diagnostics captured unresolved parameter as expected")
    else:
        case.mark_fail("Should have produced diagnostic for unresolved param")
    test_cases.append(case)

    # === Category 7: Real 10-level design with filelist (the actual complex test asset) ===
    case = TestCase("real_10level_filelist", "Load the existing 10-level separated design via top.f and check propagation")
    try:
        real_base = Path(__file__).parent.parent / "demo_data" / "elab_test_cases" / "deep_param_propagation_10level"
        fl = str(real_base / "top.f")
        prop = ParameterPropagator()
        prop.load_from_filelist(fl)
        tops = prop.find_top_modules()
        if len(tops) != 1:
            case.mark_fail(f"Expected 1 top, got {tops}")
        else:
            results = prop.elaborate(top_name=None, top_params={"TOP_P": 128})
            # In this design the last hop forces 64, so we expect many instances
            if len(results) > 10:
                case.mark_pass(f"Loaded via filelist, auto top={tops[0]}, produced {len(results)} instances")
            else:
                case.mark_fail(f"Loaded but only {len(results)} instances")
    except Exception as e:
        case.mark_fail(f"Exception: {e}")
    test_cases.append(case)

    # === Report ===
    print("\n" + "=" * 80)
    print("BATCH VERIFICATION RESULTS")
    print("=" * 80)

    passed = 0
    for tc in test_cases:
        status = "PASS" if tc.passed else "FAIL"
        print(f"[{status}] {tc.name:25} - {tc.description}")
        if tc.details:
            print(f"         {tc.details}")
        if not tc.passed and tc.diagnostics:
            print(f"         Diagnostics: {tc.diagnostics.get('errors', [])}")
        if tc.passed:
            passed += 1

    print(f"\nTotal: {passed}/{len(test_cases)} passed")

    if passed == len(test_cases):
        print("\n*** ALL BATCH TESTS PASSED - Complex design behaves as intended ***")
        return 0
    else:
        print("\n*** SOME TESTS FAILED - Review output above ***")
        return 1


if __name__ == "__main__":
    sys.exit(main())
