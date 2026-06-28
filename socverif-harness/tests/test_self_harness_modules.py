"""Unit tests for self-harness support modules (paths, baseline, weakness, verify_report)."""
# goal_build_id = 12

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import sys

sys.path.insert(0, str(ROOT))

from socverif.baseline import (  # noqa: E402
    load_baseline,
    parse_unittest_count,
    validate_self_harness_report,
    validate_unittest_count,
)
from socverif.manifest import EnvironmentManifest, resolve_project_root  # noqa: E402
from socverif.paths import is_self_harness_root, manifest_path, report_path  # noqa: E402
from socverif.runner import TierResult  # noqa: E402
from socverif.verify_report import verify  # noqa: E402
from socverif.weakness import mine_weaknesses  # noqa: E402


class TestPaths(unittest.TestCase):
    def test_self_harness_artifact_paths(self):
        self.assertTrue(is_self_harness_root(ROOT))
        self.assertEqual(
            manifest_path(ROOT).relative_to(ROOT).as_posix(),
            ".socverif/scratch/environment_manifest.yaml",
        )
        self.assertEqual(
            report_path(ROOT).relative_to(ROOT).as_posix(),
            ".socverif/scratch/verif_report.json",
        )

    def test_non_self_env_uses_root(self):
        env = ROOT / "envs/minimal_soc"
        self.assertFalse(is_self_harness_root(env))
        self.assertEqual(manifest_path(env).name, "environment_manifest.yaml")


class TestManifestRoot(unittest.TestCase):
    def test_scratch_manifest_resolves_project_root(self):
        scratch_m = ROOT / ".socverif/scratch/environment_manifest.yaml"
        if not scratch_m.is_file():
            subprocess.run(
                [sys.executable, "-m", "socverif.cli", "discover", str(ROOT)],
                cwd=ROOT, check=True, capture_output=True, env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            )
        m = EnvironmentManifest.load(scratch_m)
        self.assertEqual(m.root.resolve(), ROOT.resolve())
        self.assertTrue(m.raw.get("self_harness"))


class TestBaseline(unittest.TestCase):
    def test_baseline_loads(self):
        spec = load_baseline()
        from socverif.constants import GOAL_BUILD_ID

        self.assertEqual(spec.get("goal_build_id"), GOAL_BUILD_ID)
        self.assertEqual(spec.get("self_harness_tier_count"), 3)

    def test_validate_passing_report(self):
        spec = load_baseline()
        report = {
            "all_passed": True,
            "results": [{"tier": 0, "name": "unit_tests", "passed": True, "duration_sec": 10}],
        }
        manifest = {
            "tiers": [
                {"tier": 0, "name": "unit_tests"},
                {"tier": 1, "name": "selftest"},
                {"tier": 2, "name": "reference_envs"},
            ]
        }
        self.assertEqual(validate_self_harness_report(report, manifest, spec), [])

    def test_validate_unittest_count_meets_baseline(self):
        spec = load_baseline()
        minimum = spec["min_unit_tests"]
        self.assertEqual(validate_unittest_count(minimum, spec), [])
        self.assertEqual(validate_unittest_count(minimum - 1, spec), [
            f"unit test count {minimum - 1} < baseline {minimum}",
        ])

    def test_parse_unittest_count(self):
        self.assertEqual(parse_unittest_count("Ran 71 tests in 1.2s\n\nOK\n"), 71)


class TestWeakness(unittest.TestCase):
    def test_mine_timeout_failure(self):
        r = TierResult(tier=2, name="reference_envs", passed=False, sim_rc=-1, protocol="log_pattern")
        r.errors = ["sim failed rc=-1"]
        r.log_tail = "[TIMEOUT]"
        w = mine_weaknesses([r], "socverif-harness")
        self.assertEqual(len(w), 1)
        self.assertIn("timeout", w[0]["kind"])


class TestVerifyReport(unittest.TestCase):
    def test_verify_missing_report_fails(self):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="socverif_empty_") as tmp:
            rc, errors = verify(Path(tmp))
            self.assertEqual(rc, 1)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()