"""round_paths.jsonl — sole source for emit/bundle/final_response."""
# goal_build_id = 12

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.delivery_bundle import build_bundle  # noqa: E402
from socverif.round_paths import _normalize_rel, mark_round_start, note, paths_since  # noqa: E402


class TestRoundPathsUnified(unittest.TestCase):
    MARKER = ROOT / "tests" / ".round_paths_unified_marker"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="round_paths_unified_")
        self.addCleanup(self._cleanup_tmp)
        self.log = Path(self.tmp) / "round_paths.jsonl"
        self.round_ts = Path(self.tmp) / "round_start_ts"
        self.round_ts.write_text("2026-06-28T07:00:00Z\n", encoding="utf-8")
        os.environ["SOCVERIF_ROUND_PATHS_LOG"] = str(self.log)
        self.env = {
            **dict(os.environ),
            "PYTHONPATH": str(ROOT),
            "SOCVERIF_ROUND_PATHS_LOG": str(self.log),
            "SOCVERIF_ROUND_SINCE": str(self.round_ts),
        }
        mark_round_start(self.round_ts)

    def tearDown(self):
        os.environ.pop("SOCVERIF_ROUND_PATHS_LOG", None)

    def _cleanup_tmp(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)
        if self.MARKER.is_file():
            self.MARKER.unlink()

    def _run_script(self, script: str) -> list[str]:
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts" / script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    def test_normalize_rel_preserves_dot_socverif(self):
        self.assertEqual(_normalize_rel(".socverif/baseline.json"), ".socverif/baseline.json")
        self.assertEqual(_normalize_rel("./docs/eda_tool.md"), "docs/eda_tool.md")

    def test_touch_unifies_emit_bundle_final(self):
        self.MARKER.write_text("unified_touch\n", encoding="utf-8")
        note("tests/.round_paths_unified_marker", since_file=self.round_ts)
        rel = "tests/.round_paths_unified_marker"
        self.assertEqual(paths_since(self.round_ts, log_path=self.log), [rel])
        emit_paths = self._run_script("emit_round_changed_paths.sh")
        bundle_paths = build_bundle(self.round_ts).get("paths", [])
        final_paths = self._run_script("final_response_paths.sh")
        self.assertEqual(emit_paths, [rel])
        self.assertEqual(bundle_paths, [rel])
        self.assertEqual(final_paths, [rel])

    def test_goal_final_forces_gate_only(self):
        self.MARKER.write_text("goal_final_touch\n", encoding="utf-8")
        note("tests/.round_paths_unified_marker", since_file=self.round_ts)
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts/emit_final_response.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                **self.env,
                "SOCVERIF_GOAL_FINAL": "1",
                "SOCVERIF_UNITTEST_COUNT": "125",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("GATE_ONLY", proc.stdout)
        self.assertNotIn("FINAL_PATHS", proc.stdout)
        self.assertNotIn("tests/", proc.stdout)

    def test_empty_log_gate_only_final_response(self):
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts/emit_final_response.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**self.env, "SOCVERIF_UNITTEST_COUNT": "125"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("GATE_ONLY", proc.stdout)
        self.assertIn("zero harness source edits", proc.stdout)
        self.assertIn("unittest=125", proc.stdout)
        self.assertNotIn("tests/", proc.stdout)
        lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("tests/")]
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()