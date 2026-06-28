"""Runner log hygiene + VLP dedup — real shipped code paths."""
# goal_build_id = 12

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.manifest import EnvironmentManifest  # noqa: E402
from socverif.runner import run_all_tiers  # noqa: E402
from socverif.sim_log import prepare_logs  # noqa: E402
from socverif.toy_policy import check_toy_first, is_toy_env  # noqa: E402
from socverif.vlp import parse_vlp  # noqa: E402


class TestVlpDedup(unittest.TestCase):
    def test_parse_vlp_uses_last_summary_only(self):
        text = (
            "VERIF PASS old_run ok\nVERIF SUMMARY pass=99 fail=0 total=99 result=PASS\n"
            "VERIF PASS env_sanity ok\nVERIF SUMMARY pass=1 fail=0 total=1 result=PASS\n"
        )
        v = parse_vlp(text)
        self.assertEqual(v.summary_pass, 1)
        self.assertEqual(len(v.passes), 1)
        self.assertEqual(v.passes[0], "env_sanity")

    def test_parse_vlp_collects_all_passes_before_last_summary(self):
        text = (
            "VERIF PASS sfr_batch_rmw single_rmw\n"
            "VERIF PASS toy_sfr_ctrl_read ok\n"
            "VERIF PASS toy_sram_mark_rw ok\n"
            "VERIF SUMMARY pass=3 fail=0 total=3 result=PASS\n"
        )
        v = parse_vlp(text)
        self.assertEqual(v.summary_pass, 3)
        self.assertEqual(v.passes, ["sfr_batch_rmw", "toy_sfr_ctrl_read", "toy_sram_mark_rw"])


class TestLogPrepare(unittest.TestCase):
    def test_prepare_tier_logs_removes_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "sim_logs" / "tier1.log"
            log.parent.mkdir(parents=True)
            log.write_text("stale VERIF PASS x\n", encoding="utf-8")
            prepare_logs(root, "sim_logs/*.log")
            self.assertFalse(log.exists())


class TestToyPolicy(unittest.TestCase):
    def test_toy_mimic_is_toy(self):
        self.assertTrue(is_toy_env(ROOT / "envs/toy_mimic_soc"))

    def test_unknown_env_blocked_by_cli(self):
        with tempfile.TemporaryDirectory(prefix="nontoy_") as tmp:
            proc = subprocess.run(
                [sys.executable, "-m", "socverif.cli", "run", tmp, "--max-tier", "0"],
                cwd=ROOT, capture_output=True, text=True,
                env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("toy_policy", proc.stderr + proc.stdout)

    def test_allow_full_soc_override(self):
        with tempfile.TemporaryDirectory(prefix="nontoy_") as tmp:
            try:
                check_toy_first(Path(tmp), allow_full_soc=True, command="run")
            except SystemExit as e:
                self.fail(f"should not exit: {e}")

    def test_discover_blocked_on_non_toy(self):
        with tempfile.TemporaryDirectory(prefix="nontoy_") as tmp:
            proc = subprocess.run(
                [sys.executable, "-m", "socverif.cli", "discover", tmp],
                cwd=ROOT, capture_output=True, text=True,
                env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("toy_policy", proc.stderr + proc.stdout)

    def test_inspect_blocked_on_non_toy(self):
        with tempfile.TemporaryDirectory(prefix="nontoy_") as tmp:
            proc = subprocess.run(
                [sys.executable, "-m", "socverif.cli", "inspect", tmp, "--json"],
                cwd=ROOT, capture_output=True, text=True,
                env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            )
            self.assertEqual(proc.returncode, 2)


class TestDiscoverLogHygiene(unittest.TestCase):
    def test_discover_prepares_logs(self):
        env = ROOT / "envs/toy_mimic_soc"
        stale = env / "sim_logs" / "tier0.log"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("stale VERIF PASS old ok\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "socverif.cli", "discover", str(env), "--max-tier", "2"],
            cwd=ROOT, capture_output=True, text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(stale.exists(), "discover must clear stale tier logs")


class TestMinimalSocMaxTierReport(unittest.TestCase):
    def test_loop_max_tier2_exactly_three_results(self):
        env = ROOT / "envs/minimal_soc"
        proc = subprocess.run(
            [sys.executable, "-m", "socverif.cli", "loop", str(env), "--max-tier", "2"],
            cwd=ROOT, capture_output=True, text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        import json
        report = json.loads((env / "verif_report.json").read_text())
        self.assertTrue(report["all_passed"])
        self.assertEqual(report.get("max_tier"), 2)
        self.assertEqual(report.get("tiers_to_run"), 3)
        self.assertEqual(report.get("tiers_run"), report.get("tiers_to_run"))
        self.assertEqual(len(report["results"]), 3)
        tiers = [r["tier"] for r in report["results"]]
        self.assertEqual(tiers, [0, 1, 2])


class TestToyMimicLoopReport(unittest.TestCase):
    def test_loop_max_tier2_writes_three_results(self):
        env = ROOT / "envs/toy_mimic_soc"
        proc = subprocess.run(
            [sys.executable, "-m", "socverif.cli", "loop", str(env), "--max-tier", "2"],
            cwd=ROOT, capture_output=True, text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        import json
        report = json.loads((env / "verif_report.json").read_text())
        self.assertTrue(report["all_passed"])
        self.assertEqual(report.get("max_tier"), 2)
        self.assertEqual(report.get("tiers_to_run"), 3)
        self.assertEqual(report.get("tiers_run"), report.get("tiers_to_run"))
        self.assertEqual(len(report["results"]), 3)
        tier1 = next(r for r in report["results"] if r["tier"] == 1)
        if tier1.get("vlp"):
            self.assertLessEqual(len(tier1["vlp"].get("passes", [])), 5)


if __name__ == "__main__":
    unittest.main()