"""agent_transfer plan + dry-run apply."""

from __future__ import annotations

from pathlib import Path

from soc_verify.agent_transfer import apply_transfer_plan, build_transfer_plan
from soc_verify.env_analyze import analyze_verification_env

ROOT = Path(__file__).resolve().parents[1]


def test_build_transfer_plan_has_preflight():
    analysis = analyze_verification_env(ROOT, "VERIF-CPU-SOC")
    plan = build_transfer_plan(
        analysis=analysis,
        toy_result={"ok": True, "laps": []},
        target_project_id="VERIF-CPU-SOC",
        toy_project_id="TOY-VERIFCPU",
    )
    ids = {a["id"] for a in plan["actions"]}
    assert "install_oss_preflight" in ids
    assert plan["toy_ok"] is True


def test_apply_transfer_dry_run():
    analysis = analyze_verification_env(ROOT, "VERIF-CPU-SOC")
    plan = build_transfer_plan(
        analysis=analysis,
        toy_result={"ok": True, "laps": []},
        target_project_id="VERIF-CPU-SOC",
        toy_project_id="TOY-VERIFCPU",
    )
    result = apply_transfer_plan(ROOT, plan, apply=False, analysis=analysis)
    assert result["ok"] is True
    assert result["apply"] is False
    assert any(r["status"] == "dry_run" for r in result["results"])