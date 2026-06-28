"""Static contract — reference envs must use sim_rules.mk or sim_log CLI."""
# goal_build_id = 12

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.sim_log import audit_makefile_sim_lines, has_dual_write, sim_run_shell  # noqa: E402

REFERENCE_MAKEFILES = [
    ROOT / "envs/minimal_soc/Makefile",
    ROOT / "envs/alt_soc/sim/Makefile",
    ROOT / "envs/toy_mimic_soc/Makefile",
    ROOT / "envs/synthetic_vcs_style/Makefile",
]
SCRIPT_ONLY_RUN = ROOT / "envs/script_only_soc/scripts/run_sim.sh"


class TestSimLogContract(unittest.TestCase):
    def test_sim_run_shell_single_writer(self):
        cmd = sim_run_shell("vvp sim_build/sim.vvp", "sim_logs/tier0.log")
        self.assertIn("tee", cmd)
        self.assertNotIn("-l", cmd)
        self.assertFalse(has_dual_write(cmd))

    def test_dual_write_detected(self):
        bad = "vvp sim.vvp -l sim_logs/tier0.log 2>&1 | tee sim_logs/tier0.log"
        self.assertTrue(has_dual_write(bad))

    def test_reference_makefiles_include_sim_rules(self):
        for mf in REFERENCE_MAKEFILES:
            text = mf.read_text(encoding="utf-8")
            self.assertIn("sim_rules.mk", text, mf.name)
            self.assertNotIn("tee -a", text, mf.name)
            inline_vvp = [
                ln for ln in text.splitlines()
                if re.search(r"(?:^|\s)vvp\s", ln)
            ]
            self.assertEqual(inline_vvp, [], f"{mf.name} must not inline vvp sim")

    def test_reference_makefiles_tier_log_paths(self):
        fw_rules = (ROOT / "envs/common/fw_rules.mk").read_text(encoding="utf-8")
        for mf in REFERENCE_MAKEFILES:
            text = mf.read_text(encoding="utf-8")
            combined = text + ("\n" + fw_rules if "fw_rules.mk" in text else "")
            for tier in (0, 1):
                self.assertIn(f"tier{tier}.log", combined, f"{mf.name} tier{tier}")

    def test_script_only_uses_sim_log_module(self):
        text = SCRIPT_ONLY_RUN.read_text(encoding="utf-8")
        self.assertIn("socverif.sim_log", text)
        self.assertNotIn("tee -a", text)
        self.assertFalse(has_dual_write(text))

    def test_sim_rules_mk_has_no_dual_write(self):
        rules = (ROOT / "envs/common/sim_rules.mk").read_text(encoding="utf-8")
        violations = audit_makefile_sim_lines(rules)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()