"""classifier_anchor — sole writer bind/assert for classifier patches."""
# goal_build_id = 20

from __future__ import annotations

import json
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
from socverif.classifier_capture import mirror_changed_paths  # noqa: E402
from socverif.constants import HARNESS_ROOT  # noqa: E402



class TestClassifierAnchorBind(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="anchor_bind_")
        self.addCleanup(self._cleanup)
        self.scratch = Path(self.tmp) / "implementer"
        self.goal_root = Path(self.tmp)
        self.scratch.mkdir(parents=True)

    def _cleanup(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_note_bind_attempt_patch_matches_changed(self):
        result = bind_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        changed = result["changed_paths"]
        self.assertGreater(len(changed), 0)
        self.assertTrue(all(p.startswith("socverif-harness/") for p in changed))
        (self.goal_root / "goal-classifier-extra.patch").write_text("stale\n", encoding="utf-8")
        bind_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        assert_result = assert_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        self.assertTrue(assert_result["ok"], assert_result.get("errors"))
        allowed = set(mirror_changed_paths(changed))
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        if allowed and attempt.is_file():
            self.assertEqual(set(paths_in_patch(attempt.read_text())), allowed)

    def test_bind_overwrites_polluted_attempt_patch(self):
        goal_id = _goal_classifier_id(self.goal_root)
        polluted = (
            "diff --git a/grok-workspace/socverif-harness/foo b/grok-workspace/foo\n"
            "diff --git a/.grok/sessions/x b/.grok/sessions/x\n"
        )
        (self.goal_root / f"goal-classifier-{goal_id}-1.patch").write_text(polluted, encoding="utf-8")
        bind_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        changed = set(mirror_changed_paths(collect_round_changed_cfa_paths(HARNESS_ROOT)))
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        body = attempt.read_text(encoding="utf-8")
        patch_paths = paths_in_patch(body)
        for path in patch_paths:
            self.assertNotIn(".grok/", path, msg=f"forbidden path in {attempt.name}")
        if changed:
            self.assertEqual(set(patch_paths), changed)

    def test_historical_dirty_slot_ignored_when_attempt_clean(self):
        """Only attempt patch matters; dirty historical slots do not fail assert."""
        goal_id = _goal_classifier_id(self.goal_root)
        polluted = (
            "diff --git a/.grok/sessions/x b/.grok/sessions/x\n"
            "diff --git a/grok-workspace/socverif-harness/docs/eda_tool.md b/grok-workspace/docs/eda_tool.md\n"
        )
        (self.goal_root / f"goal-classifier-{goal_id}-5.patch").write_text(polluted, encoding="utf-8")
        (self.goal_root / f"goal-verdict-{goal_id}-1-0.json").write_text("{}", encoding="utf-8")
        (self.goal_root / f"goal-verdict-{goal_id}-2-0.json").write_text("{}", encoding="utf-8")
        (self.goal_root / f"goal-verdict-{goal_id}-3-0.json").write_text("{}", encoding="utf-8")
        (self.goal_root / f"goal-verdict-{goal_id}-4-0.json").write_text("{}", encoding="utf-8")
        bind_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        attempt = resolve_classifier_attempt_patch(self.goal_root)
        changed = set(mirror_changed_paths(collect_round_changed_cfa_paths(HARNESS_ROOT)))
        if changed:
            self.assertEqual(set(paths_in_patch(attempt.read_text())), changed)
        assert_result = assert_anchors(self.goal_root, self.scratch, harness_root=HARNESS_ROOT)
        self.assertTrue(assert_result["ok"], assert_result.get("errors"))

    def test_pre_claim_bind_script(self):
        (self.goal_root / "goal-classifier-test.patch").write_text("polluted\n", encoding="utf-8")
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts/pre_claim_bind.sh")],
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
        self.assertTrue((self.scratch / "PRE_CLAIM_BIND_DONE.log").is_file())


if __name__ == "__main__":
    unittest.main()