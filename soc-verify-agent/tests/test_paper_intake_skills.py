from __future__ import annotations

import json
from pathlib import Path

from soc_verify.knowledge_intake import collect_knowledge_bundle
from soc_verify.paper_intake_skills import (
    bootstrap_paper_intake_skills,
    collect_paper_skills_for_llm,
    list_paper_intake_skill_ids,
    paper_skills_prompt_block,
)


ROOT = Path(__file__).resolve().parents[1]


def test_list_paper_intake_skill_ids():
    ids = list_paper_intake_skill_ids(ROOT)
    assert "paper-intake-hub" in ids
    assert "paper-intake-curate" in ids
    assert "paper-progress-judge" in ids
    assert len(ids) >= 9


def test_bootstrap_installs_skills_and_obsidian_mirror(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "PAPER-SOC"
    project.mkdir(parents=True)
    _copy_registry_and_templates(root)

    result = bootstrap_paper_intake_skills(project, ROOT)
    assert result["ok"]
    assert result["count"] >= 8
    assert (project / "skills" / "paper-intake-curate" / "SKILL.md").is_file()
    assert (project / "knowledge" / "obsidian" / "04-skills" / "paper-intake-hub.md").is_file()
    assert (project / "intake" / "paper_intake_skills.json").is_file()

    block = paper_skills_prompt_block(project, ROOT)
    assert block["primary_skill"] == "paper-intake-curate"
    assert "publication" in block["instruction"].lower() or "paper" in block["instruction"].lower()

    llm_skills = collect_paper_skills_for_llm(project, ROOT)
    assert any(s["id"] == "paper-intake-curate" for s in llm_skills)


def test_collect_bootstraps_paper_skills(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "COL-SOC"
    project.mkdir(parents=True)
    (project / "discovered.yaml").write_text("project_id: COL-SOC\n", encoding="utf-8")
    _copy_registry_and_templates(root)

    collect_knowledge_bundle(root, "COL-SOC")
    assert (project / "skills" / "paper-intake-hub" / "SKILL.md").is_file()
    moc = (project / "knowledge" / "obsidian" / "05-intake" / "SOURCES-MOC.md").read_text(encoding="utf-8")
    assert "paper-intake-curate" in moc


def _copy_registry_and_templates(root: Path):
    for name in ("knowledge_intake_spec.yaml", "paper_intake_skills_spec.yaml"):
        src = ROOT / "registry" / name
        if src.is_file():
            (root / "registry").mkdir(parents=True, exist_ok=True)
            (root / "registry" / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    tpl_root = ROOT / "templates" / "skills" / "paper-intake"
    if tpl_root.is_dir():
        import shutil

        shutil.copytree(tpl_root, root / "templates" / "skills" / "paper-intake")
    (root / "config.json").write_text(json.dumps({"llm": {"mode": "stub"}}), encoding="utf-8")