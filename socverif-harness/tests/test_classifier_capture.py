# goal_build_id = 20

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.classifier_anchor import (  # noqa: E402
    _goal_classifier_id,
    assert_anchors,
    bind_anchors,
    collect_round_changed_cfa_paths,
    paths_in_patch,
    resolve_classifier_attempt_patch,
)
from socverif.classifier_capture import (  # noqa: E402
    MIRROR_NAME,
    WITNESS_NAME,
    classifier_proof_is_stale,
    mirror_changed_paths,
    mirror_path_file,
    reconcile_attempt_patch_from_witness,
    rewrite_patch_mirror_prefix,
    seal_classifier_evidence,
    simulate_outer_harness_overwrite,
    verify_attempt_patch_on_disk,
    witness_path,
)
from socverif.constants import HARNESS_ROOT  # noqa: E402


class TestClassifierCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="capture_")
        self.addCleanup(self._cleanup)
        self.scratch = Path(self.tmp) / "implementer"
        self.goal_root = Path(self.tmp)
        self.scratch.mkdir(parents=True)

    def _cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rewrite_mirror_prefix(self):
        body = "diff --git a/socverif-harness/foo b/socverif-harness/foo\n"
        mirror = rewrite_patch_mirror_prefix(body)
        self.assertIn("grok-workspace/socverif-harness/foo", mirror)
        self.assertNotIn("diff --git a/socverif-harness/", mirror)

    def test_seal_writes_witness_mirror_and_attempt_match(self):
        result = seal_classifier_evidence(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        self.assertTrue(result["verify"]["ok"], result["verify"].get("errors"))
        self.assertTrue(witness_path(self.scratch).is_file())
        self.assertTrue(mirror_path_file(self.scratch).is_file())
        self.assertTrue((self.goal_root / WITNESS_NAME).is_file())
        self.assertTrue((self.goal_root / MIRROR_NAME).is_file())
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        mirror = mirror_path_file(self.scratch).read_text(encoding="utf-8")
        self.assertEqual(mirror, attempt.read_text(encoding="utf-8"))
        disk = verify_attempt_patch_on_disk(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        self.assertTrue(disk["ok"], disk.get("errors"))

    def test_outer_classifier_overwrite_simulation(self):
        seal_classifier_evidence(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        clean_mirror = mirror_path_file(self.scratch).read_text(encoding="utf-8")
        polluted = (
            "diff --git a/.grok/sessions/x b/.grok/sessions/x\n"
            "diff --git a/grok-workspace/socverif-harness/docs/eda_tool.md b/grok-workspace/docs/eda_tool.md\n"
        )
        simulate_outer_harness_overwrite(self.goal_root, polluted)
        self.assertTrue(classifier_proof_is_stale(self.goal_root, self.scratch))
        reconcile_attempt_patch_from_witness(self.goal_root, self.scratch)
        self.assertEqual(attempt.read_text(encoding="utf-8"), clean_mirror)
        disk = verify_attempt_patch_on_disk(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        self.assertTrue(disk["ok"], disk.get("errors"))

    def test_mirror_paths_align_with_changed(self):
        seal_classifier_evidence(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        changed = collect_round_changed_cfa_paths(HARNESS_ROOT)
        if not changed:
            return
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        patch_paths = set(paths_in_patch(attempt.read_text(encoding="utf-8")))
        self.assertEqual(patch_paths, set(mirror_changed_paths(changed)))
        for p in patch_paths:
            self.assertNotIn(".grok/", p)

    def test_freeze_classifier_script(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts/freeze_classifier_snapshot.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                **dict(__import__("os").environ),
                "PYTHONPATH": str(ROOT),
                "SCRATCH": str(self.scratch),
                "SOCVERIF_GOAL_ROOT": str(self.goal_root),
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertTrue((self.scratch / "FREEZE_CLASSIFIER_DONE.log").is_file())
        proof = json.loads((self.scratch / "freeze_on_disk_proof.json").read_text())
        self.assertTrue(proof["mirror_match_attempt"])
        self.assertFalse(proof["has_grok_path"])


class TestClassifierAnchorFreezeDelegate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="anchor_freeze_")
        self.addCleanup(self._cleanup)
        self.scratch = Path(self.tmp) / "implementer"
        self.goal_root = Path(self.tmp)
        self.scratch.mkdir(parents=True)

    def _cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bind_delegates_to_seal(self):
        goal_id = _goal_classifier_id(self.goal_root)
        polluted = "diff --git a/.grok/sessions/x b/.grok/sessions/x\n"
        (self.goal_root / f"goal-classifier-{goal_id}-1.patch").write_text(polluted, encoding="utf-8")
        bind_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        for path in paths_in_patch(attempt.read_text(encoding="utf-8")):
            self.assertNotIn(".grok/", path)
        assert_result = assert_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        self.assertTrue(assert_result["ok"], assert_result.get("errors"))


if __name__ == "__main__":
    unittest.main()