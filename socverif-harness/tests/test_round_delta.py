"""Per-round harness delta from hunk_records."""
# goal_build_id = 12

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.round_delta import (  # noqa: E402
    check_round_delta,
    harness_paths_since,
    load_since_file,
)


class TestRoundDelta(unittest.TestCase):
    def _write_hunk(self, path: Path, records: list[dict]) -> None:
        path.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )

    def test_harness_paths_since_filters_by_timestamp(self):
        since = datetime(2026, 6, 27, 18, 0, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            hunk = Path(tmp) / "hunk_records.jsonl"
            self._write_hunk(hunk, [
                {
                    "filePath": str(ROOT / "socverif/cli.py"),
                    "timestamp": "2026-06-27T17:59:00Z",
                },
                {
                    "filePath": str(ROOT / "socverif/round_delta.py"),
                    "timestamp": "2026-06-27T18:05:00Z",
                },
                {
                    "filePath": "/home/user/tools/hierwalk/foo.py",
                    "timestamp": "2026-06-27T18:10:00Z",
                },
            ])
            paths = harness_paths_since(since, hunk)
            self.assertEqual(paths, ["socverif/round_delta.py"])

    def test_check_round_delta_minimum(self):
        since = datetime(2026, 6, 27, 18, 0, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            hunk = Path(tmp) / "hunk_records.jsonl"
            self._write_hunk(hunk, [
                {
                    "filePath": str(ROOT / "docs/success_flow.md"),
                    "timestamp": "2026-06-27T18:01:00Z",
                },
            ])
            ok = check_round_delta(since, minimum=1, hunk_path=hunk)
            self.assertTrue(ok["ok"])
            self.assertEqual(ok["count"], 1)

    def test_load_since_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "round_start_ts"
            marker.write_text("2026-06-27T18:02:15Z\n", encoding="utf-8")
            ts = load_since_file(marker)
            self.assertEqual(ts.year, 2026)
            self.assertEqual(ts.month, 6)


if __name__ == "__main__":
    unittest.main()