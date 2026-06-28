"""classifier_evidence — source-only CHANGED_FILES + patch honesty."""
# goal_build_id = 14

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.classifier_evidence import (  # noqa: E402
    HARNESS_PREFIX,
    build_round_paths_patch,
    collect_round_changed_cfa_paths,
    paths_in_patch,
    sync_classifier_evidence,
    sync_deliverable_tree,
    validate_patch_honesty,
    workspace_harness_root,
    write_changed_files,
)
from socverif.constants import HARNESS_ROOT  # noqa: E402
from socverif.workspace_delta import scrub_workspace_artifacts  # noqa: E402


class TestClassifierEvidence(unittest.TestCase):
    def test_sync_deliverable_tree_excludes_artifacts(self):
        with tempfile.TemporaryDirectory() as ws:
            synced = sync_deliverable_tree(Path(ws), cfa_harness=HARNESS_ROOT)
            dest = workspace_harness_root(Path(ws))
            self.assertTrue((dest / "socverif/cli.py").is_file())
            self.assertTrue((dest / "envs/toy_mimic_soc/Makefile").is_file())
            self.assertFalse((dest / "envs/toy_mimic_soc/environment_manifest.yaml").is_file())
            self.assertFalse(any(dest.glob("*.egg-info")))
            self.assertGreater(len(synced), 50)

    def test_patch_honesty_rejects_egg_info(self):
        changed = ["socverif-harness/docs/a.md"]
        bad = "diff --git a/socverif-harness/foo.egg-info/bar b/foo\n"
        errors = validate_patch_honesty(bad, changed)
        self.assertTrue(any("egg-info" in e or "not in CHANGED" in e for e in errors))

    def test_changed_files_match_round_paths_only(self):
        scratch = Path(tempfile.mkdtemp(prefix="classifier_sync_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(scratch, ignore_errors=True))
        result = sync_classifier_evidence(
            scratch=scratch,
            goal_root=scratch,
            cfa_harness=HARNESS_ROOT,
        )
        round_paths = collect_round_changed_cfa_paths(HARNESS_ROOT)
        changed = [
            ln.strip()
            for ln in (scratch / "CHANGED_FILES").read_text().splitlines()
            if ln.strip()
        ]
        self.assertEqual(changed, result["changed_paths"])
        self.assertEqual(len(changed), len(round_paths))
        diff = (scratch / "goal-code-changes.diff").read_text()
        patch_paths = paths_in_patch(diff)
        if changed and patch_paths:
            self.assertEqual(set(patch_paths), set(changed))
            self.assertFalse(any("egg-info" in p for p in patch_paths))

    def test_build_round_paths_patch_no_artifacts(self):
        changed = collect_round_changed_cfa_paths(HARNESS_ROOT)
        if not changed:
            self.skipTest("no round paths this round")
        body = build_round_paths_patch(changed[:3])
        for p in paths_in_patch(body):
            self.assertNotIn("egg-info", p)
            self.assertIn(p, changed[:3])

    def test_scrub_workspace_removes_egg_info(self):
        with tempfile.TemporaryDirectory() as ws:
            dest = workspace_harness_root(Path(ws))
            dest.mkdir(parents=True)
            egg = dest / "socverif_harness.egg-info"
            egg.mkdir()
            (egg / "PKG-INFO").write_text("x\n", encoding="utf-8")
            removed = scrub_workspace_artifacts(dest)
            self.assertFalse(egg.exists())
            self.assertTrue(any("egg-info" in r for r in removed))

    def test_sync_tree_cli_entry(self):
        with tempfile.TemporaryDirectory() as ws:
            scratch = Path(ws) / "scratch"
            scratch.mkdir()
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "socverif.classifier_evidence",
                    "sync-tree",
                    "--cfa-harness",
                    str(HARNESS_ROOT),
                    "--workspace",
                    ws,
                    "--scratch",
                    str(scratch),
                ],
                cwd=HARNESS_ROOT,
                capture_output=True,
                text=True,
                env={**dict(__import__("os").environ), "PYTHONPATH": str(HARNESS_ROOT)},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            meta = json.loads((scratch / "sync_tree.json").read_text())
            self.assertTrue(meta["has_cli"])
            self.assertTrue(meta["has_toy_mimic"])
            self.assertFalse(meta["has_egg_info"])
            self.assertFalse(meta["toy_has_manifest"])

    def test_write_changed_files_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "CHANGED_FILES"
            write_changed_files(["socverif-harness/a.py", "socverif-harness/b.py"], dest)
            self.assertEqual(
                dest.read_text().strip().splitlines(),
                ["socverif-harness/a.py", "socverif-harness/b.py"],
            )


if __name__ == "__main__":
    unittest.main()