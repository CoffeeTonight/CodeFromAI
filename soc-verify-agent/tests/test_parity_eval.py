from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from soc_verify.parity_eval import (
    LLM_REFERENCE_NAME,
    PARITY_REPORT_NAME,
    compare_verdicts,
    parity_allows_promote,
    run_parity_check,
    snapshot_llm_reference,
)
from soc_verify.registry_writer import apply_promotion


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def _run_dir() -> Path:
    d = EXAMPLE / "runs" / f"parity-test-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_compare_verdicts_match_and_mismatch():
    ref = {"status": "PASS", "log_scan": {"ok": True}, "tiers": {"t1": {"ok": True}}}
    py_ok = dict(ref)
    py_bad = {"status": "FAIL", "log_scan": {"ok": False}}

    assert compare_verdicts(ref, py_ok)["ok"] is True
    report = compare_verdicts(ref, py_bad)
    assert report["ok"] is False
    assert any("status" in i for i in report["issues"])


def test_snapshot_and_parity_check(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    group = "gpio_ext"
    verdict = {"status": "PASS", "gate": group}
    (run_dir / f"verdict_{group}.json").write_text(json.dumps(verdict), encoding="utf-8")

    snapshot_llm_reference(run_dir, group)
    assert (run_dir / LLM_REFERENCE_NAME).is_file()

    report = run_parity_check(run_dir, group, python_verdict=verdict)
    assert report["ok"] is True
    assert (run_dir / PARITY_REPORT_NAME).is_file()
    ok, reason = parity_allows_promote(run_dir)
    assert ok is True
    assert reason == "parity_ok"


def test_registry_writer_blocks_promote_without_parity():
    run_dir = _run_dir()
    (run_dir / "promote_decision.md").write_text("decision: approve\n", encoding="utf-8")

    outcome = apply_promotion(
        EXAMPLE,
        "gpio_ext.py",
        trust_score=0.9,
        run_dir=run_dir,
    )
    assert outcome["promoted"] is False
    assert outcome["reason"] == "missing_parity_report"


def test_registry_writer_allows_promote_with_parity_ok():
    run_dir = _run_dir()
    (run_dir / "promote_decision.md").write_text("decision: approve\n", encoding="utf-8")
    (run_dir / PARITY_REPORT_NAME).write_text(
        json.dumps({"ok": True, "contract": "parity_eval_v1"}),
        encoding="utf-8",
    )

    reg_before = (EXAMPLE / "trust" / "registry.yaml").read_text(encoding="utf-8")
    try:
        outcome = apply_promotion(
            EXAMPLE,
            "gpio_ext.py",
            trust_score=0.9,
            run_dir=run_dir,
        )
        assert outcome["promoted"] is True
    finally:
        (EXAMPLE / "trust" / "registry.yaml").write_text(reg_before, encoding="utf-8")