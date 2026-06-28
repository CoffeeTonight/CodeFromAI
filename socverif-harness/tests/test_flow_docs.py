"""Contract tests for flow documentation (eda_tool, soc_validation_flow, success/failed_flow)."""
# goal_build_id = 12

from __future__ import annotations

import unittest
from pathlib import Path

from tests.flow_doc_terms import (
    EDA_TOOL_TERMS,
    FAILED_TERMS,
    REQUIRED_DOCS,
    SOC_VALIDATION_TERMS,
    SUCCESS_TERMS,
)

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


class TestFlowDocsExist(unittest.TestCase):
    def test_all_required_docs_exist(self):
        for name in REQUIRED_DOCS:
            path = DOCS / name
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_readme_references_flow_docs(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in REQUIRED_DOCS:
            self.assertIn(name, readme, f"README must reference docs/{name}")


class TestSocValidationFlowContent(unittest.TestCase):
    def test_required_terms_present(self):
        text = (DOCS / "soc_validation_flow.md").read_text(encoding="utf-8")
        for term in SOC_VALIDATION_TERMS:
            self.assertIn(term, text, f"soc_validation_flow.md missing: {term}")


class TestEdaToolContent(unittest.TestCase):
    def test_eda_and_harness_terms(self):
        text = (DOCS / "eda_tool.md").read_text(encoding="utf-8")
        for term in EDA_TOOL_TERMS:
            self.assertIn(term, text, f"eda_tool.md missing: {term}")


class TestSuccessFailedFlowContent(unittest.TestCase):
    def test_success_flow_has_timing_records(self):
        text = (DOCS / "success_flow.md").read_text(encoding="utf-8")
        for term in SUCCESS_TERMS:
            self.assertIn(term, text, f"success_flow.md missing: {term}")

    def test_failed_flow_has_dissection(self):
        text = (DOCS / "failed_flow.md").read_text(encoding="utf-8")
        for term in FAILED_TERMS:
            self.assertIn(term, text, f"failed_flow.md missing: {term}")


if __name__ == "__main__":
    unittest.main()