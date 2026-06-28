"""Goal acceptance criteria (plan.md) — integration gates beyond flow_doc_terms."""
# goal_build_id = 12

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.flow_doc_terms import REQUIRED_DOCS, SOC_VALIDATION_TERMS

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))

from socverif.constants import GOAL_BUILD_ID  # noqa: E402
from socverif.hunk_tracking import LOCAL_HUNK_PATH, resolve_hunk_sources  # noqa: E402
from socverif.round_delta import load_since_file  # noqa: E402
from socverif.toy_policy import is_toy_env  # noqa: E402
from socverif.user_methods import check_user_methods  # noqa: E402

SELF_VERIFY_SCRIPTS = (
    "scripts/self_verify_pr.sh",
    "scripts/self_verify_nightly.sh",
    "scripts/self_harness_repeat.sh",
    "scripts/run_goal_verification.sh",
    "scripts/docs_check.sh",
    "scripts/emit_round_changed_paths.sh",
    "scripts/note_round_path.sh",
)


class TestGoalAcceptanceCriteria(unittest.TestCase):
    """plan.md ## Acceptance criteria — integration-only checks."""

    def test_goal_build_id_matches_deliverable(self):
        spec = json.loads((ROOT / "GOAL_DELIVERABLE.json").read_text(encoding="utf-8"))
        self.assertEqual(GOAL_BUILD_ID, spec["goal_build_id"])

    def test_criterion_4_toy_mimic_enforcement(self):
        toy_root = ROOT / "envs/toy_mimic_soc"
        self.assertTrue((toy_root / ".socverif/toy_mimic.yaml").is_file())
        self.assertTrue(is_toy_env(toy_root))
        with tempfile.TemporaryDirectory(prefix="nontoy_accept_") as tmp:
            proc = subprocess.run(
                [sys.executable, "-m", "socverif.cli", "loop", tmp, "--max-tier", "0"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("toy_policy", proc.stderr + proc.stdout)

    def test_criterion_5_readme_and_self_verify_paths(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in REQUIRED_DOCS:
            self.assertIn(name, readme, f"README must reference docs/{name}")
        for script in SELF_VERIFY_SCRIPTS:
            path = ROOT / script
            self.assertTrue(path.is_file(), script)
            self.assertTrue(path.stat().st_mode & 0o111, f"{script} not executable")

    def test_user_methods_merged_in_flow(self):
        result = check_user_methods()
        self.assertTrue(result["ok"], result)
        self.assertIn("example_sfr_batch", result["merged"][0])

    def test_portable_hunk_sources_available(self):
        sources = resolve_hunk_sources()
        self.assertTrue(sources, "at least one hunk source must exist")
        flow = (ROOT / "docs/soc_validation_flow.md").read_text(encoding="utf-8")
        for term in ("TAT tier", "example_sfr_batch"):
            self.assertIn(term, flow)

    def test_round_delta_marker_loadable(self):
        marker = ROOT / ".socverif/round_start_ts"
        self.assertTrue(marker.is_file())
        ts = load_since_file(marker)
        self.assertIsNotNone(ts.tzinfo)

    def test_local_hunk_path_under_socverif(self):
        self.assertEqual(LOCAL_HUNK_PATH.parent.name, ".socverif")

    def test_docs_check_script_passes(self):
        with tempfile.TemporaryDirectory(prefix="goal_docs_check_") as tmp:
            out = Path(tmp) / "docs_check.log"
            proc = subprocess.run(
                ["bash", str(ROOT / "scripts/docs_check.sh"), str(out)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("DOCS_CHECK_PASS", text)
            self.assertIn("USER_METHODS_CHECK_PASS", text)

    def test_flow_terms_delegated_to_shared_module(self):
        self.assertIn("SFR내 bit field 개별 접근 금지", SOC_VALIDATION_TERMS)


if __name__ == "__main__":
    unittest.main()