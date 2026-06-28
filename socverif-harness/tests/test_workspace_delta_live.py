"""Live workspace_delta — snapshot source_paths; tests restore production snapshot."""
# goal_build_id = 12

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.round_paths import note, preflight_final_claims  # noqa: E402
from socverif.workspace_delta import (  # noqa: E402
    _is_git_repo,
    capture_snapshot,
    changed_paths_since,
    git_changed_paths,
    is_deliverable_source,
)
from socverif.delivery_bundle import build_bundle  # noqa: E402


class TestWorkspaceDeltaLive(unittest.TestCase):
    MARKER = ROOT / "tests" / ".workspace_delta_touch_marker"
    SNAP = ROOT / ".socverif" / "workspace_snapshot.json"

    def setUp(self):
        self.round_ts = ROOT / ".socverif" / "round_start_ts"
        self._snap_backup = self.SNAP.read_text(encoding="utf-8") if self.SNAP.is_file() else None
        self._round_ts_backup = (
            self.round_ts.read_text(encoding="utf-8") if self.round_ts.is_file() else None
        )
        self.round_ts.write_text("2026-06-28T06:00:00Z\n", encoding="utf-8")
        capture_snapshot(self.round_ts)

    def tearDown(self):
        if self.MARKER.is_file():
            self.MARKER.unlink()
        if self._snap_backup is not None:
            self.SNAP.write_text(self._snap_backup, encoding="utf-8")
        elif self.SNAP.is_file():
            self.SNAP.unlink(missing_ok=True)
        if self._round_ts_backup is not None:
            self.round_ts.write_text(self._round_ts_backup, encoding="utf-8")

    def test_touch_file_appears_in_git_delta(self):
        if not _is_git_repo():
            self.skipTest("harness not in a git work tree")
        self.MARKER.write_text("workspace_delta_live_touch\n", encoding="utf-8")
        paths = git_changed_paths()
        self.assertIn("tests/.workspace_delta_touch_marker", paths)

    def test_changed_paths_since_matches_bundle(self):
        import os
        import tempfile

        log = Path(tempfile.mkdtemp()) / "round_paths.jsonl"
        os.environ["SOCVERIF_ROUND_PATHS_LOG"] = str(log)
        self.addCleanup(os.environ.pop, "SOCVERIF_ROUND_PATHS_LOG", None)
        from socverif.round_paths import mark_round_start

        mark_round_start(self.round_ts)
        self.MARKER.write_text("bundle_match_touch\n", encoding="utf-8")
        note("tests/.workspace_delta_touch_marker", since_file=self.round_ts)
        bundle = build_bundle(self.round_ts)
        self.assertIn("tests/.workspace_delta_touch_marker", bundle["paths"])

    def test_preflight_final_claims_ok_after_touch(self):
        import os
        import tempfile

        log = Path(tempfile.mkdtemp()) / "round_paths.jsonl"
        os.environ["SOCVERIF_ROUND_PATHS_LOG"] = str(log)
        self.addCleanup(os.environ.pop, "SOCVERIF_ROUND_PATHS_LOG", None)
        from socverif.round_paths import mark_round_start

        mark_round_start(self.round_ts)
        self.MARKER.write_text("preflight_touch\n", encoding="utf-8")
        note("tests/.workspace_delta_touch_marker", since_file=self.round_ts)
        result = preflight_final_claims(self.round_ts)
        self.assertTrue(result["ok"])
        self.assertTrue(result["paths_match_bundle"])
        self.assertIn("tests/.workspace_delta_touch_marker", result["round_paths"])

    def test_empty_snapshot_diff_does_not_use_git(self):
        delta = changed_paths_since(self.round_ts)
        self.assertEqual(delta["source"], "snapshot")
        self.assertEqual(delta["paths"], [])

    def test_metadata_paths_excluded_from_delivery(self):
        from socverif.workspace_delta import partition_paths

        parts = partition_paths(
            [
                "docs/soc_validation_flow.md",
                ".socverif/DELIVERY_BUNDLE.json",
                ".socverif/scratch/run.log",
                "tests/.workspace_delta_touch_marker",
            ]
        )
        self.assertEqual(
            parts["source_paths"],
            ["docs/soc_validation_flow.md", "tests/.workspace_delta_touch_marker"],
        )
        self.assertIn(".socverif/DELIVERY_BUNDLE.json", parts["metadata_paths"])
        self.assertFalse(is_deliverable_source(".socverif/DELIVERY_BUNDLE.json"))


if __name__ == "__main__":
    unittest.main()