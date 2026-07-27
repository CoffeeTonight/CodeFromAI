"""env_analyze unit tests."""

from __future__ import annotations

from pathlib import Path

from soc_verify.env_analyze import analyze_verification_env

ROOT = Path(__file__).resolve().parents[1]


def test_analyze_verif_cpu_project():
    report = analyze_verification_env(ROOT, "VERIF-CPU-SOC")
    assert report["contract"] == "env_analyze_v1"
    assert report["project_id"] == "VERIF-CPU-SOC"
    assert report.get("rtl_root")
    assert "ops_scripts" in report
    assert "verification_groups" in report
    assert report["finding_counts"]["total"] >= 0
    # flow replay
    flow = report.get("flow") or {}
    assert flow.get("contract") == "env_flow_v1"
    assert (flow.get("paradigm") or {}).get("primary") == "cpu_fw"
    assert report.get("toy_requirements", {}).get("paradigm") == "cpu_fw"