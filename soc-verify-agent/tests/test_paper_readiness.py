from __future__ import annotations

import json
from pathlib import Path

from soc_verify.experiment import resolve_experiment_tags, write_experiment_run
from soc_verify.paper_export import export_paper
from soc_verify.paper_readiness import (
    assess_paper_readiness,
    format_readiness_summary,
    write_readiness_report,
)
from soc_verify.platform_telemetry import ensure_platform_baseline


ROOT = Path(__file__).resolve().parents[1]


def _seed_registry(tmp_root: Path) -> None:
    reg = tmp_root / "registry"
    reg.mkdir(parents=True)
    for name in (
        "evaluation_manifest.yaml",
        "experiment_spec.yaml",
        "paper_readiness_spec.yaml",
        "platform_baseline.yaml",
        "platform_telemetry.yaml",
        "code_change_log.yaml",
    ):
        src = ROOT / "registry" / name
        if src.is_file():
            (reg / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _make_run(
    root: Path,
    *,
    project: str,
    run_id: str,
    campaign: str,
    condition: str,
    verdict: str = "PASS",
) -> Path:
    run_dir = root / "projects" / project / "runs" / run_id
    run_dir.mkdir(parents=True)
    write_experiment_run(
        run_dir,
        resolve_experiment_tags(root, campaign=campaign, condition=condition, hypothesis="H1"),
    )
    (run_dir / "improvement_snapshot.json").write_text(
        json.dumps(
            {
                "stage": "simulation",
                "group": "gpio_ext",
                "verdict": verdict,
                "improvement_index": 0.9,
                "trust_score": 0.85,
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def test_assess_paper_readiness_empty_campaign(tmp_path: Path):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")

    report = assess_paper_readiness(root, "empty_camp")
    assert report["contract"] == "paper_readiness_v1"
    assert report["overall_percent"] < 50
    assert report["paper_ready"] is False
    assert report["verdict"] in ("bootstrap", "early_stage")
    dims = {d["id"]: d for d in report["dimensions"]}
    assert dims["experiment_design"]["gaps"]


def test_assess_paper_readiness_with_runs(tmp_path: Path):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")
    campaign = "paper_test"

    for i in range(5):
        _make_run(root, project="EXAMPLE-SOC", run_id=f"ctrl{i}", campaign=campaign, condition="control")
    for i in range(5):
        _make_run(root, project="EXAMPLE-SOC", run_id=f"trt{i}", campaign=campaign, condition="treatment_full")

    report = assess_paper_readiness(root, campaign)
    assert report["run_count"] == 10
    assert report["overall_percent"] >= 40
    exp_dim = next(d for d in report["dimensions"] if d["id"] == "experiment_design")
    assert exp_dim["score"] >= 0.7
    assert "Next actions" in format_readiness_summary(report)


def test_export_paper_includes_readiness(tmp_path: Path):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")
    campaign = "exp_readiness"
    _make_run(root, project="EXAMPLE-SOC", run_id="r1", campaign=campaign, condition="treatment_full")

    out = root / "exports" / campaign
    result = export_paper(root, campaign, out)
    assert "paper_readiness_percent" in result
    assert (out / "paper_readiness.json").is_file()
    assert (out / "paper_readiness.md").is_file()
    readiness = json.loads((out / "paper_readiness.json").read_text(encoding="utf-8"))
    assert readiness["campaign"] == campaign


def test_write_readiness_report(tmp_path: Path):
    root = tmp_path / "ws"
    _seed_registry(root)
    ensure_platform_baseline(root, trigger="test")
    campaign = "write_test"
    _make_run(root, project="EXAMPLE-SOC", run_id="r1", campaign=campaign, condition="control")

    path = write_readiness_report(root, campaign)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["campaign"] == campaign