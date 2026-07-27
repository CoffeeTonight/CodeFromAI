"""agent settle — reflect residual into toy (unit)."""

from __future__ import annotations

from pathlib import Path

from soc_verify.agent_settle import load_mission, reflect_residuals_into_toy
from soc_verify.toy_intake import resolve_toy_intake
from soc_verify.toy_scaffold import scaffold_toy_project

ROOT = Path(__file__).resolve().parents[1]


def test_mission_file_exists():
    m = load_mission(ROOT)
    assert m.get("contract") == "agent_mission_v1"
    primary = m.get("primary") or {}
    text = str(primary.get("purpose_ko") or m.get("purpose_ko") or "")
    assert "오류" in text or "탐지" in text or "detect" in text.lower()


def test_reflect_writes_lesson_into_toy(tmp_path: Path):
    # use real VERIF-CPU intake but scaffold under unique toy id in workspace
    toy_id = "TOY-SETTLE-UNIT"
    project = ROOT / "projects" / toy_id
    if project.is_dir():
        import shutil

        shutil.rmtree(project)
    spec = resolve_toy_intake(ROOT, source_id="VERIF-CPU-SOC")
    scaffold_toy_project(ROOT, spec, project_id=toy_id, overwrite=True)

    out = reflect_residuals_into_toy(
        ROOT,
        toy_project_id=toy_id,
        residuals=[
            {
                "kind": "production_probe",
                "severity": "high",
                "verdict": "FAIL",
                "group": "oss_preflight",
                "evidence": [
                    "production oss_preflight verdict=FAIL",
                    "missing OSS artifact: firmware/campaign/build/missing_probe.bin",
                ],
                "fix_to_toy": "add check",
            }
        ],
        production_project="VERIF-CPU-SOC",
        round_idx=1,
    )
    assert out["residual_count"] == 1
    assert Path(out["lesson_path"]).is_file()
    assert Path(out["pattern_path"]).is_file()
    assert "firmware/campaign/build/missing_probe.bin" in (out.get("promoted_artifacts") or [])
    import shutil

    shutil.rmtree(project)
