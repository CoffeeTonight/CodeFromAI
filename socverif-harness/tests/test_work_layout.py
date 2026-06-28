# goal_build_id = 20

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.work_layout import (  # noqa: E402
    MIRROR_PATH_PREFIX,
    goal_root,
    goal_scratch,
    outer_workspace_root,
    tools_root,
    work_root,
)


class TestWorkLayout(unittest.TestCase):
    def test_default_under_tools_not_tmp(self):
        with tempfile.TemporaryDirectory(prefix="tools_") as tmp:
            os.environ["SOCVERIF_TOOLS_ROOT"] = tmp
            os.environ.pop("SOCVERIF_WORK_ROOT", None)
            os.environ.pop("SOCVERIF_GOAL_ROOT", None)
            os.environ.pop("SCRATCH", None)
            os.environ.pop("GROK_WORKSPACE_ROOT", None)
            wr = work_root()
            sc = goal_scratch()
            gr = goal_root()
            self.assertEqual(wr, Path(tmp) / "socverif-harness-work")
            self.assertEqual(gr, wr / "goal")
            self.assertEqual(sc, gr / "implementer")
            self.assertNotIn("/tmp/grok-goal", str(sc))
            ow = outer_workspace_root()
            self.assertEqual(ow, wr / "grok-workspace")

    def test_scratch_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SCRATCH"] = tmp
            self.assertEqual(goal_scratch(), Path(tmp).resolve())

    def test_tools_root_from_cfa_location(self):
        os.environ.pop("SOCVERIF_TOOLS_ROOT", None)
        tr = tools_root()
        self.assertTrue(tr.is_dir())
        self.assertEqual(tr.name, "tools")

    def test_mirror_prefix_unchanged(self):
        self.assertEqual(MIRROR_PATH_PREFIX, "grok-workspace/socverif-harness/")


if __name__ == "__main__":
    unittest.main()