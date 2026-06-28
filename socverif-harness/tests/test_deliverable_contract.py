"""Contract tests — deliverable paths, selftest gate, questa_trap EDA (goal_build_id = 12)."""
# goal_build_id = 12

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "envs"

sys.path.insert(0, str(ROOT))

from socverif.constants import GOAL_BUILD_ID  # noqa: E402
from socverif.discovery.eda_stage import detect_eda  # noqa: E402
from socverif.preflight import check_hunk_tracking, hunk_tracking_required  # noqa: E402


class TestDeliverableContract(unittest.TestCase):
    def test_goal_build_id(self):
        spec = json.loads((ROOT / "GOAL_DELIVERABLE.json").read_text(encoding="utf-8"))
        self.assertEqual(GOAL_BUILD_ID, spec["goal_build_id"])

    def test_goal_deliverable_json_lists_required_paths(self):
        spec = json.loads((ROOT / "GOAL_DELIVERABLE.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["goal_build_id"], GOAL_BUILD_ID)
        missing = [p for p in spec["required_paths"] if not (ROOT / p).exists()]
        self.assertEqual(missing, [], f"missing deliverable paths: {missing}")

    def test_questa_trap_returns_iverilog_not_questa(self):
        eda = detect_eda(FIXTURES / "questa_trap")
        self.assertEqual(eda.simulator, "iverilog")
        self.assertNotEqual(eda.simulator, "questa")

    def test_goal_session_hunk_tracking_optional(self):
        result = check_hunk_tracking()
        self.assertFalse(result["required"])
        self.assertTrue(result["ok"])

    def test_goal_session_hunk_tracking_when_required(self):
        if not hunk_tracking_required():
            result = check_hunk_tracking(required=True)
            if not result["hunk_exists"]:
                self.skipTest("goal session hunk_records not available in this environment")
            self.assertTrue(result["required"])
            self.assertTrue(result["ok"], result)
            self.assertGreaterEqual(result["count"], 30)

    def test_selftest_subprocess_passes(self):
        with tempfile.TemporaryDirectory(prefix="socverif_selftest_") as tmp:
            scratch = Path(tmp)
            proc = subprocess.run(
                [sys.executable, "-m", "socverif.selftest", "--scratch", str(scratch), "--skip-pip"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                env={**dict(os.environ), "PYTHONPATH": str(ROOT)},
            )
            summary = scratch / "SELFTEST_SUMMARY.txt"
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(summary.exists(), "selftest must write SELFTEST_SUMMARY.txt")
            self.assertIn("PASS", summary.read_text(encoding="utf-8"))

    def test_self_harness_manifest_present(self):
        manifest = ROOT / ".socverif" / "manifest.yaml"
        baseline = ROOT / ".socverif" / "baseline.json"
        self.assertTrue(manifest.is_file())
        self.assertTrue(baseline.is_file())
        spec = json.loads(baseline.read_text(encoding="utf-8"))
        self.assertGreaterEqual(spec.get("min_unit_tests", 0), 45)

    def test_verification_plan_subprocess_passes(self):
        with tempfile.TemporaryDirectory(prefix="socverif_plan_") as tmp:
            scratch = Path(tmp)
            proc = subprocess.run(
                ["bash", str(ROOT / "scripts/run_verification_plan.sh")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                env={**dict(os.environ), "PYTHONPATH": str(ROOT), "SCRATCH": str(scratch)},
            )
            done = scratch / "VERIFICATION_PLAN_DONE.log"
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(done.exists(), "verification plan must write VERIFICATION_PLAN_DONE.log")
            self.assertIn("PASS", done.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()