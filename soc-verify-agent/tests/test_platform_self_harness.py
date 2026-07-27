"""Platform-minimal self-harness weakness mining."""

from __future__ import annotations

import json
from pathlib import Path

from soc_verify.platform_self_harness import mine_weaknesses, write_weakness_report
from soc_verify.self_harness import integrate_training_finalize_weakness

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_mine_weaknesses_from_verdict_fail(tmp_path: Path):
    project_dir = tmp_path / "EXAMPLE-SOC"
    run_dir = project_dir / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (tmp_path / "registry").mkdir()
    spec_src = ROOT / "registry" / "self_harness_spec.yaml"
    if spec_src.is_file():
        (tmp_path / "registry" / "self_harness_spec.yaml").write_text(
            spec_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (run_dir / "verdict_gpio_ext.json").write_text(
        json.dumps({"verdict": "FAIL", "summary": "sim mismatch"}),
        encoding="utf-8",
    )
    signals = {
        "run_id": "r1",
        "project_id": "EXAMPLE-SOC",
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "FAIL",
    }
    report = mine_weaknesses(tmp_path, project_dir, run_dir, signals=signals)
    assert report["contract"] == "weakness_report_v1"
    assert any(w["category"] == "verification_gap" for w in report["weaknesses"])


def test_integrate_training_finalize_weakness_writes_artifact(tmp_path: Path):
    project_dir = tmp_path / "EXAMPLE-SOC"
    run_dir = project_dir / "runs" / "r-train"
    run_dir.mkdir(parents=True)
    (tmp_path / "registry").mkdir()
    (run_dir / "graph_trace.jsonl").write_text(
        '{"node":"finalize","verdict":"PASS"}\n', encoding="utf-8"
    )
    (run_dir / "verdict_gpio_ext.json").write_text(
        json.dumps({"verdict": "PASS"}), encoding="utf-8"
    )
    state = {
        "run_id": "r-train",
        "project_id": "EXAMPLE-SOC",
        "project_dir": str(project_dir),
        "stage": "simulation",
        "group": "gpio_ext",
        "verdict": "PASS",
        "run_profile": "training",
        "events": {},
    }
    result = integrate_training_finalize_weakness(tmp_path, project_dir, run_dir, state)
    assert result["ok"] is True
    assert (run_dir / "weakness_report.json").is_file()
    assert (run_dir / "improvement_signal.json").is_file()