from __future__ import annotations

import json
from pathlib import Path

from soc_verify.paper_progress import (
    build_mechanical_judgment,
    build_puzzle_pieces,
    merge_judgment,
    render_progress_mermaid,
    sync_paper_progress,
)
from soc_verify.paper_readiness import assess_paper_readiness


ROOT = Path(__file__).resolve().parents[1]


def _copy_specs(root: Path):
    for name in ("paper_readiness_spec.yaml", "paper_progress_spec.yaml", "evaluation_manifest.yaml"):
        src = ROOT / "registry" / name
        if src.is_file():
            (root / "registry").mkdir(parents=True, exist_ok=True)
            (root / "registry" / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def test_puzzle_pieces_have_percents(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "PP-SOC"
    project.mkdir(parents=True)
    (project / "state.yaml").write_text("current_milestone: M2\n", encoding="utf-8")
    _copy_specs(root)

    from soc_verify.paper_progress import load_spec

    report = assess_paper_readiness(root, "paper_eval_2026")
    pieces = build_puzzle_pieces(report, project, load_spec(root))
    assert len(pieces) >= 7
    assert all("percent" in p for p in pieces)
    assert pieces[0]["id"] == "intake"


def test_mermaid_contains_percent():
    judgment = {
        "puzzle_pieces": [
            {"id": "intake", "label_ko": "수집", "percent": 65},
            {"id": "experiment", "label_ko": "실험", "percent": 20},
        ]
    }
    md = render_progress_mermaid(judgment)
    assert "65%" in md
    assert "flowchart LR" in md


def test_sync_writes_progress_vault(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "VAULT-SOC"
    project.mkdir(parents=True)
    (project / "state.yaml").write_text("x: 1\n", encoding="utf-8")
    _copy_specs(root)
    import shutil

    shutil.copytree(
        ROOT / "templates" / "skills" / "paper-intake",
        root / "templates" / "skills" / "paper-intake",
    )

    from soc_verify.paper_intake_skills import bootstrap_paper_intake_skills

    bootstrap_paper_intake_skills(project, ROOT)

    result = sync_paper_progress(root, "VAULT-SOC", "paper_eval_2026")
    assert result["ok"]
    progress = project / "knowledge" / "obsidian" / "06-paper" / "PROGRESS.md"
    assert progress.is_file()
    text = progress.read_text(encoding="utf-8")
    assert "mermaid" in text
    assert "overall_percent" in (project / "knowledge" / "obsidian" / "06-paper" / "paper_progress.json").read_text()
    assert (project / "intake" / "paper_progress_prompt.json").is_file()
    assert (project / "intake" / "paper_progress_judgment.json").is_file()


def test_merge_llm_judgment_overrides_summary(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "P"
    project.mkdir(parents=True)
    mech = build_mechanical_judgment(
        {"overall_percent": 40, "verdict": "early_stage", "dimensions": [], "section_status": [], "next_actions": []},
        project,
        root,
        campaign="c",
        project_id="P",
    )
    llm = {"source": "llm", "llm_summary_ko": "LLM: 병목은 실험 설계", "top_gaps": ["gap1"]}
    merged = merge_judgment(mech, llm)
    assert merged["llm_summary_ko"] == "LLM: 병목은 실험 설계"
    assert merged["source"] == "mechanical+llm"