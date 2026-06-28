"""Delivery bundle — paths must match round_paths.jsonl."""
# goal_build_id = 12

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.delivery_bundle import build_bundle, write_bundle  # noqa: E402
from socverif.round_paths import mark_round_start, note, paths_since  # noqa: E402


class TestDeliveryHonesty(unittest.TestCase):
    TOUCH = ROOT / "tests" / ".delivery_honesty_touch_marker"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="delivery_honesty_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = Path(self.tmp) / "round_paths.jsonl"
        self.round_ts = Path(self.tmp) / "round_start_ts"
        self.round_ts.write_text("2026-06-28T07:01:00Z\n", encoding="utf-8")
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
        if self.TOUCH.is_file():
            self.TOUCH.unlink()

    def test_bundle_matches_round_paths(self):
        self.TOUCH.write_text("delivery_honesty\n", encoding="utf-8")
        note("tests/.delivery_honesty_touch_marker", since_file=self.round_ts)
        rp = paths_since(self.round_ts, log_path=self.log)
        bundle = build_bundle(self.round_ts)
        self.assertEqual(sorted(rp), sorted(bundle["paths"]))
        self.assertGreaterEqual(bundle["count"], 1)

    def test_final_response_paths_script_matches_bundle(self):
        self.TOUCH.write_text("final_paths\n", encoding="utf-8")
        note("tests/.delivery_honesty_touch_marker", since_file=self.round_ts)
        bundle = build_bundle(self.round_ts)
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts/final_response_paths.sh")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        script_paths = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        self.assertEqual(sorted(script_paths), sorted(bundle["paths"]))

    def test_write_bundle_to_scratch(self):
        self.TOUCH.write_text("scratch_bundle\n", encoding="utf-8")
        note("tests/.delivery_honesty_touch_marker", since_file=self.round_ts)
        scratch = Path(tempfile.mkdtemp(prefix="delivery_scratch_"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        bundle = build_bundle(self.round_ts)
        out = write_bundle(scratch, bundle)
        self.assertTrue(out.is_file())
        loaded = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(loaded["count"], bundle["count"])


if __name__ == "__main__":
    unittest.main()