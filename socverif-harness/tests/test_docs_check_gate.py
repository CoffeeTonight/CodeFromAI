"""docs_check.sh must fail on missing keywords (no false PASS echo)."""
# goal_build_id = 12

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestDocsCheckGate(unittest.TestCase):
    def test_docs_check_fails_without_toy_mimic_soc(self):
        with tempfile.TemporaryDirectory() as tmp:
            mini = ROOT / "envs" / "minimal_soc"
            fake = Path(tmp) / "fake_harness"
            (fake / "docs").mkdir(parents=True)
            (fake / "socverif").mkdir(parents=True)
            (fake / "scripts").mkdir(parents=True)
            (fake / "envs/minimal_soc").mkdir(parents=True)
            for name in ("eda_tool.md", "soc_validation_flow.md", "success_flow.md", "failed_flow.md"):
                shutil.copy2(ROOT / "docs" / name, fake / "docs" / name)
            for mod in ("cli.py", "runner.py", "vlp.py", "manifest.py", "constants.py", "user_methods.py"):
                shutil.copy2(ROOT / "socverif" / mod, fake / "socverif" / mod)
            shutil.copy2(ROOT / "scripts/docs_check.sh", fake / "scripts/docs_check.sh")
            shutil.copytree(mini, fake / "envs/minimal_soc", dirs_exist_ok=True)
            proc = subprocess.run(
                ["bash", str(fake / "scripts/docs_check.sh"), f"{tmp}/bad.log"],
                cwd=fake,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(fake)},
            )
            self.assertNotEqual(proc.returncode, 0)
            text = Path(f"{tmp}/bad.log").read_text(encoding="utf-8")
            self.assertIn("MISSING toy_mimic_soc", text)

    def test_docs_check_passes_on_real_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                ["bash", str(ROOT / "scripts/docs_check.sh"), f"{tmp}/ok.log"],
                cwd=ROOT, capture_output=True, text=True,
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = Path(f"{tmp}/ok.log").read_text(encoding="utf-8")
            self.assertIn("DOCS_CHECK_PASS", text)
            self.assertIn("USER_METHODS_CHECK_PASS", text)


if __name__ == "__main__":
    unittest.main()