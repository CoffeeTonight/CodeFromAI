"""agent bootcamp — analyze + scaffold + transfer dry-run (skip heavy laps)."""

from __future__ import annotations

from pathlib import Path

from soc_verify.agent_bootcamp import run_agent_bootcamp

ROOT = Path(__file__).resolve().parents[1]


def test_bootcamp_skip_laps_dry_transfer():
    out = run_agent_bootcamp(
        ROOT,
        source_project="VERIF-CPU-SOC",
        toy_project_id="TOY-BOOTCAMP-TEST",
        overwrite=True,
        apply=False,
        skip_toy_laps=True,
    )
    assert out["contract"] == "agent_bootcamp_v1"
    assert out["source_project"] == "VERIF-CPU-SOC"
    assert out["toy_project"] == "TOY-BOOTCAMP-TEST"
    assert (ROOT / "projects" / "TOY-BOOTCAMP-TEST" / "ops" / "sanity" / "oss_smoke.py").is_file()
    assert (ROOT / "projects" / "VERIF-CPU-SOC" / "reports" / "agent_bootcamp" / "BOOTCAMP.md").is_file()
    assert out["transfer"]["apply"] is False
