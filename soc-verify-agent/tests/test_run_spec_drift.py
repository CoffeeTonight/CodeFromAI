from __future__ import annotations

from pathlib import Path

from soc_verify.run_spec import compute_drift, freeze_run_spec

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_drift_detects_check_change(tmp_path: Path):
    project = tmp_path / "proj"
    stage, group = "simulation", "gpio_ext"
    gdir = project / "verification" / stage / group
    gdir.mkdir(parents=True)
    check = gdir / "CHECK.md"
    check.write_text("# CHECK v1\n", encoding="utf-8")
    (gdir / "manifest.yaml").write_text("gates: []\n", encoding="utf-8")
    (project / "cache.yaml").write_text("tag:\n  value: v1\n", encoding="utf-8")

    run_dir = project / "runs" / "r1"
    run_dir.mkdir(parents=True)
    freeze_run_spec(project, run_dir, stage=stage, group=group, as_of="2026-06-19")

    check.write_text("# CHECK v2 changed\n", encoding="utf-8")
    report = compute_drift(project, run_dir, stage=stage, group=group)
    assert report["drift_score"] >= 1.0
    assert report["ok"] is False
    assert "check_md_changed" in report["reasons"]