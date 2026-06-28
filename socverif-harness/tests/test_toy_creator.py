"""toy-create CLI scaffolds toy from user env."""
# goal_build_id = 12

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.toy_creator import create_toy_mimic  # noqa: E402


class TestToyCreator(unittest.TestCase):
    def test_create_from_minimal_soc(self):
        out_parent = ROOT / ".socverif" / "scratch" / "toy_create_test"
        if out_parent.exists():
            shutil.rmtree(out_parent)
        out_parent.mkdir(parents=True)
        out = create_toy_mimic(ROOT / "envs/minimal_soc", out_name="minimal_clone_toy", out_parent=out_parent)
        self.assertTrue((out / ".socverif/toy_mimic.yaml").is_file())
        self.assertTrue((out / "Makefile").is_file())
        self.assertTrue((out / "include/toy_regs.h").is_file())
        header = (out / "include/toy_regs.h").read_text(encoding="utf-8")
        self.assertIn("SFR_CTRL", header)

    def test_toy_create_loop_e2e_sfr_batch_in_log_and_vlp(self):
        out_parent = ROOT / ".socverif" / "scratch" / "toy_e2e_loop"
        if out_parent.exists():
            shutil.rmtree(out_parent)
        out_parent.mkdir(parents=True)
        out = create_toy_mimic(ROOT / "envs/minimal_soc", out_name="e2e_toy", out_parent=out_parent)
        env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
        subprocess.run(
            [sys.executable, "-m", "socverif.cli", "loop", str(out), "--max-tier", "2"],
            cwd=ROOT, check=True, capture_output=True, text=True, env=env,
        )
        log = (out / "sim_logs/tier2.log").read_text(encoding="utf-8")
        self.assertIn("sfr_batch_rmw", log)
        report = json.loads((out / "verif_report.json").read_text(encoding="utf-8"))
        tier2 = [r for r in report["results"] if r["tier"] == 2][0]
        self.assertIn("sfr_batch_rmw", tier2["vlp"]["passes"])

    def test_cli_toy_create_subprocess(self):
        out_parent = ROOT / ".socverif" / "scratch" / "toy_create_cli"
        if out_parent.exists():
            shutil.rmtree(out_parent)
        proc = subprocess.run(
            [
                sys.executable, "-m", "socverif.cli", "toy-create",
                str(ROOT / "envs/minimal_soc"),
                "--name", "cli_toy", "--out-dir", str(out_parent),
            ],
            cwd=ROOT, capture_output=True, text=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((out_parent / "cli_toy").is_dir())


if __name__ == "__main__":
    unittest.main()