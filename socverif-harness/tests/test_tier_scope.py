"""Tier scope — discovered vs runnable must stay aligned."""
# goal_build_id = 12

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.manifest import EnvironmentManifest, tier_scope_summary, tiers_to_run  # noqa: E402


class TestTierScope(unittest.TestCase):
    def test_tiers_to_run_max_tier2(self):
        m = EnvironmentManifest.load(ROOT / "envs/minimal_soc/environment_manifest.yaml")
        if not (ROOT / "envs/minimal_soc/environment_manifest.yaml").is_file():
            subprocess.run(
                [sys.executable, "-m", "socverif.cli", "discover",
                 str(ROOT / "envs/minimal_soc"), "--max-tier", "2"],
                cwd=ROOT, check=True, capture_output=True,
                env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            )
            m = EnvironmentManifest.load(ROOT / "envs/minimal_soc/environment_manifest.yaml")
        scope = tier_scope_summary(m, max_tier=2)
        runnable = tiers_to_run(m, max_tier=2)
        self.assertGreaterEqual(scope["discovered"], 3)
        self.assertEqual(scope["to_run"], 3)
        self.assertEqual(len(runnable), 3)
        self.assertEqual([t.tier for t in runnable], [0, 1, 2])

    def test_discover_print_matches_scope(self):
        proc = subprocess.run(
            [sys.executable, "-m", "socverif.cli", "discover",
             str(ROOT / "envs/minimal_soc"), "--max-tier", "2"],
            cwd=ROOT, capture_output=True, text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("tiers_discovered=", proc.stdout)
        self.assertIn("tiers_to_run=3", proc.stdout)
        self.assertIn("max_tier=2", proc.stdout)
        self.assertNotRegex(proc.stdout, r"\[discover\] tiers=\d+$")


if __name__ == "__main__":
    unittest.main()