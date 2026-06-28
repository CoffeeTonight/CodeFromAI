"""fw_gen — register symbol classification and HOST_VERIF codegen."""
# goal_build_id = 12

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.fw_gen import classify_reg_syms, generate_verif_tests, parse_reg_header  # noqa: E402


class TestFwGen(unittest.TestCase):
    def test_classify_toy_sfr_symbols(self):
        header = ROOT / "envs/toy_mimic_soc/include/toy_regs.h"
        syms = parse_reg_header(header)
        sfr, sram = classify_reg_syms(syms)
        self.assertIn("TOY_SFR_CTRL", sfr)
        self.assertIn("TOY_SRAM_MARK", sram)

    def test_generated_tests_not_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "verif"
            generate_verif_tests(ROOT / "envs/toy_mimic_soc/include/toy_regs.h", out)
            text = (out / "verif_tests.c").read_text(encoding="utf-8")
            self.assertIn("sfr_batch_rmw", text)
            self.assertIn("TOY_SFR_CTRL", text)
            self.assertNotIn('verif_log_pass("noop"', text)

    def test_fw_tier2_compiles_and_runs(self):
        env = ROOT / "envs/toy_mimic_soc"
        subprocess.run(
            [sys.executable, "-m", "socverif.cli", "instrument", str(env)],
            cwd=ROOT, check=True, capture_output=True,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        proc = subprocess.run(
            ["make", "sim-tier2"],
            cwd=env, capture_output=True, text=True, check=False,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        log = (env / "sim_logs/tier2.log").read_text(encoding="utf-8")
        self.assertIn("VERIF SUMMARY", log)
        self.assertIn("result=PASS", log)
        self.assertIn("sfr_batch_rmw", log)


if __name__ == "__main__":
    unittest.main()