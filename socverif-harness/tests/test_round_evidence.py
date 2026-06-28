"""Round evidence — round_paths aligned with delivery_bundle."""
# goal_build_id = 12

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.round_evidence import build_round_evidence, write_round_evidence  # noqa: E402
from socverif.round_paths import mark_round_start, note  # noqa: E402


class TestRoundEvidence(unittest.TestCase):
    TOUCH = ROOT / "tests" / ".round_evidence_touch_marker"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="round_evidence_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.log = Path(self.tmp) / "round_paths.jsonl"
        self.round_ts = Path(self.tmp) / "round_start_ts"
        self.round_ts.write_text("2026-06-28T06:01:00Z\n", encoding="utf-8")
        os.environ["SOCVERIF_ROUND_PATHS_LOG"] = str(self.log)
        self.scratch = Path(self.tmp) / "scratch"
        mark_round_start(self.round_ts)
        self.TOUCH.write_text("evidence_touch\n", encoding="utf-8")
        note("tests/.round_evidence_touch_marker", since_file=self.round_ts)

    def tearDown(self):
        if self.TOUCH.is_file():
            self.TOUCH.unlink()
        os.environ.pop("SOCVERIF_ROUND_PATHS_LOG", None)

    def test_build_round_evidence_paths_match(self):
        ev = build_round_evidence(self.round_ts)
        self.assertTrue(ev["paths_match_bundle"])
        self.assertIn("tests/.round_evidence_touch_marker", ev["source_paths"])

    def test_write_round_evidence_json(self):
        out = write_round_evidence(self.scratch, self.round_ts)
        self.assertTrue(out.is_file())
        loaded = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(loaded["ok"])


if __name__ == "__main__":
    unittest.main()