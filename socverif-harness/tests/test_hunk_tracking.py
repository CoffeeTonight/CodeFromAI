"""Portable hunk tracking — local + multi-source round delta."""
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

from socverif.hunk_tracking import (  # noqa: E402
    LOCAL_HUNK_PATH,
    append_local_records,
    collect_tracked_paths,
    resolve_hunk_sources,
)
from socverif.round_delta import harness_paths_since  # noqa: E402


class TestHunkTracking(unittest.TestCase):
    def test_append_local_records_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "hunk_records.jsonl"
            # Patch via direct write mimicking append logic
            ts = datetime(2026, 6, 28, 12, 0, 0, tzinfo=timezone.utc)
            from socverif import hunk_tracking as ht

            orig = ht.LOCAL_HUNK_PATH
            ht.LOCAL_HUNK_PATH = local
            try:
                n = ht.append_local_records(["socverif/cli.py"], timestamp=ts)
                self.assertEqual(n, 1)
                self.assertTrue(local.is_file())
                text = local.read_text(encoding="utf-8")
                self.assertIn("socverif/cli.py", text)
            finally:
                ht.LOCAL_HUNK_PATH = orig

    def test_resolve_hunk_sources_includes_local_when_present(self):
        sources = resolve_hunk_sources()
        self.assertTrue(sources)

    def test_harness_paths_since_per_source(self):
        since = datetime(2026, 6, 27, 18, 0, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            hunk = Path(tmp) / "a.jsonl"
            hunk.write_text(
                json.dumps({
                    "filePath": str(ROOT / "docs/eda_tool.md"),
                    "timestamp": "2026-06-27T18:01:00Z",
                }) + "\n",
                encoding="utf-8",
            )
            paths = harness_paths_since(since, hunk_path=hunk)
            self.assertEqual(paths, ["docs/eda_tool.md"])

    def test_collect_tracked_paths_from_explicit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            hunk = Path(tmp) / "hunk.jsonl"
            hunk.write_text(
                json.dumps({
                    "filePath": str(ROOT / "tests/test_hunk_tracking.py"),
                    "timestamp": "2026-06-27T18:00:00Z",
                }) + "\n",
                encoding="utf-8",
            )
            paths = collect_tracked_paths([hunk])
            self.assertTrue(any("test_hunk_tracking.py" in p for p in paths))

    def test_local_hunk_path_constant(self):
        self.assertEqual(LOCAL_HUNK_PATH.name, "hunk_records.jsonl")


if __name__ == "__main__":
    unittest.main()