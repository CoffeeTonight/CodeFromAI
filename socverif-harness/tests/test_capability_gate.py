"""Capability gate — toy report VLP + TAT checks."""
# goal_build_id = 12

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.capability_gate import (  # noqa: E402
    CapabilityAcquireConfig,
    check_toy_loop_tat,
    check_toy_report,
    summarize_acquire,
)


class TestCapabilityGate(unittest.TestCase):
    def _sample_report(self) -> dict:
        return {
            "all_passed": True,
            "max_tier": 2,
            "tiers_to_run": 3,
            "tiers_run": 3,
            "results": [
                {"tier": 0, "vlp": {"result": "PASS", "passes": []}},
                {"tier": 1, "vlp": {"result": "PASS", "passes": []}},
                {
                    "tier": 2,
                    "vlp": {
                        "passes": ["sfr_batch_rmw", "sram_marker_rw"],
                        "summary": {"result": "PASS", "pass": 2, "fail": 0, "total": 2},
                    },
                },
            ],
        }

    def test_check_toy_report_pass(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(self._sample_report(), fh)
            path = Path(fh.name)
        try:
            result = check_toy_report(path)
            self.assertTrue(result["ok"])
            self.assertIn("sfr_batch_rmw", result["vlp_passes"])
        finally:
            path.unlink(missing_ok=True)

    def test_check_toy_report_missing_pass(self):
        bad = self._sample_report()
        bad["results"][2]["vlp"]["passes"] = []
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(bad, fh)
            path = Path(fh.name)
        try:
            result = check_toy_report(path)
            self.assertFalse(result["ok"])
            self.assertIn("sfr_batch_rmw", result["missing_passes"])
        finally:
            path.unlink(missing_ok=True)

    def test_check_toy_loop_tat(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
            fh.write("toy_mimic_elapsed 2.5\n")
            path = Path(fh.name)
        try:
            ok = check_toy_loop_tat(path, ceiling=30.0)
            self.assertTrue(ok["ok"])
            self.assertAlmostEqual(ok["elapsed_sec"], 2.5)
        finally:
            path.unlink(missing_ok=True)


    def test_summarize_acquire_checklist(self):
        probe = {"ok": True}
        report = self._sample_report()
        cfg = CapabilityAcquireConfig(required_streak=3, toy_loop_repeat=3)
        summary = summarize_acquire(
            streak=3,
            rounds=3,
            config=cfg,
            probe=probe,
            toy_create_report=report,
            toy_create_log_has_sfr=True,
        )
        self.assertTrue(summary.ok)
        self.assertIn("SELF_HARNESS_CAPABILITY_ACQUIRED", summary.message)


if __name__ == "__main__":
    unittest.main()