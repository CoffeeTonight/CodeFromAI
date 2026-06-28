"""plan.md unittest literals must match baseline.json."""
# goal_build_id = 12

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.baseline import load_baseline  # noqa: E402
from socverif.plan_contract import (  # noqa: E402
    check_plan_contract,
    scan_acceptance_numbers,
    scan_plan_literals,
)


class TestPlanContract(unittest.TestCase):
    def test_goal_plan_matches_baseline(self):
        plan = Path(
            "/home/user/.grok/sessions/%2Fhome%2Fuser/"
            "019f0539-43e8-76f0-a3ec-b6a269d83593/goal/plan.md"
        )
        if not plan.is_file():
            self.skipTest("goal plan.md not in this environment")
        result = check_plan_contract(plan)
        minimum = load_baseline()["min_unit_tests"]
        self.assertTrue(result["ok"], f"mismatches vs {minimum}: {result.get('mismatches')}")
        self.assertEqual(result.get("defects", []), [], result.get("defects"))

    def test_live_goal_plan_acceptance_sequential(self):
        plan = Path(
            "/home/user/.grok/sessions/%2Fhome%2Fuser/"
            "019f0539-43e8-76f0-a3ec-b6a269d83593/goal/plan.md"
        )
        if not plan.is_file():
            self.skipTest("goal plan.md not in this environment")
        nums = scan_acceptance_numbers(plan.read_text(encoding="utf-8"))
        self.assertEqual(nums, [1, 2, 3, 4], f"acceptance numbering: {nums}")

    def test_mangled_ac_label_space_form_detected(self):
        """Detect '10 4. Toy-first...' mangled label (space form, not only arrow)."""
        minimum = load_baseline()["min_unit_tests"]
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(
                "## Acceptance criteria\n"
                "10 4. Toy-first + repeatable self-harness bad label\n"
                f"unittest={minimum}\n"
            )
        path = Path(fh.name)
        try:
            result = check_plan_contract(path)
            self.assertFalse(result["ok"])
            kinds = [d["kind"] for d in result.get("defects", [])]
            self.assertIn("mangled_ac_label", kinds)
        finally:
            path.unlink(missing_ok=True)

    def test_mangled_ac_label_detected(self):
        minimum = load_baseline()["min_unit_tests"]
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(
                f"## Acceptance criteria\n10 4. Toy-first bad label\nunittest={minimum}\n"
            )
            path = Path(fh.name)
        try:
            result = check_plan_contract(path)
            self.assertFalse(result["ok"])
            kinds = [d["kind"] for d in result.get("defects", [])]
            self.assertIn("mangled_ac_label", kinds)
        finally:
            path.unlink(missing_ok=True)

    def test_artifact_arrow_detected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("## Acceptance criteria\n10→4. bad line\nunittest=108\n")
            path = Path(fh.name)
        try:
            result = check_plan_contract(path)
            self.assertFalse(result["ok"])
            kinds = [d["kind"] for d in result.get("defects", [])]
            self.assertIn("artifact_arrow", kinds)
        finally:
            path.unlink(missing_ok=True)

    def test_mismatch_detected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("GOAL_VERIFICATION_PASS unittest=1\nran>=99\n")
            path = Path(fh.name)
        try:
            result = check_plan_contract(path)
            self.assertFalse(result["ok"])
            self.assertGreaterEqual(len(result["mismatches"]), 1)
        finally:
            path.unlink(missing_ok=True)

    def test_scan_finds_multiple_kinds(self):
        minimum = load_baseline()["min_unit_tests"]
        text = f"unittest={minimum}\nRan {minimum} tests\nmin_unit_tests=={minimum}\nran>={minimum}\n"
        hits = scan_plan_literals(text)
        self.assertGreaterEqual(len(hits), 3)


if __name__ == "__main__":
    unittest.main()