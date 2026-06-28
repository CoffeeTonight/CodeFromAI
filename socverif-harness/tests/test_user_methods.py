"""User verification method merge gate."""
# goal_build_id = 12

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from socverif.user_methods import (  # noqa: E402
    check_user_methods,
    is_referenced_in_flow,
    list_method_files,
)


class TestUserMethods(unittest.TestCase):
    def test_example_method_listed(self):
        methods = list_method_files()
        names = [m.name for m in methods]
        self.assertIn("example_sfr_batch.md", names)

    def test_example_referenced_in_flow(self):
        flow = (ROOT / "docs/soc_validation_flow.md").read_text(encoding="utf-8")
        example = ROOT / "docs/methods/example_sfr_batch.md"
        self.assertTrue(is_referenced_in_flow(example, flow))

    def test_check_user_methods_passes(self):
        result = check_user_methods()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["method_count"], 1)

    def test_unmerged_method_fails_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            methods = Path(tmp) / "methods"
            methods.mkdir()
            flow = Path(tmp) / "flow.md"
            (methods / "orphan.md").write_text("# orphan\n", encoding="utf-8")
            flow.write_text("# flow without reference\n", encoding="utf-8")
            from socverif import user_methods as um

            orig_dir = um.METHODS_DIR
            orig_flow = um.FLOW_DOC
            um.METHODS_DIR = methods
            try:
                result = um.check_user_methods(flow_path=flow)
                self.assertFalse(result["ok"])
                self.assertIn("orphan.md", result["missing_in_flow"][0])
            finally:
                um.METHODS_DIR = orig_dir
                um.FLOW_DOC = orig_flow


if __name__ == "__main__":
    unittest.main()