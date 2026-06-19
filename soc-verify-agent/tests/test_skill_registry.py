from __future__ import annotations

from pathlib import Path

from soc_verify.skill_registry import (
    delete_skill,
    get_skill,
    list_skills,
    load_registry,
    register_skill,
    register_skillset_from_text,
    update_skill,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"


def test_register_skill_and_list(tmp_path: Path):
    project = tmp_path / "TEST-PROJ"
    project.mkdir()
    entry = register_skill(
        project,
        name="Block sanity compile",
        body="# Block sanity\n\nRun block compile gate.",
        milestone_ids=["M2"],
        tags=["sanity"],
    )
    assert entry["id"]
    skills = list_skills(project)
    assert len(skills) == 1
    assert skills[0]["name"] == "Block sanity compile"
    assert "M2" in skills[0]["milestone_ids"]


def test_register_skillset_from_text_parses_blocks(tmp_path: Path):
    project = tmp_path / "TEST-PROJ"
    project.mkdir()
    text = """# UVM smoke
Run block UVM smoke test.

---
Chip sim nightly
Kick chip-level regression."""
    entries = register_skillset_from_text(project, text, default_milestone="M3")
    assert len(entries) == 2
    assert (project / "skills" / "intake.md").is_file()
    registry = load_registry(project)
    assert len(registry["skills"]) == 2


def test_update_and_delete_skill(tmp_path: Path):
    project = tmp_path / "TEST-PROJ"
    project.mkdir()
    entry = register_skill(project, name="Lint", body="# Lint\n", skill_id="lint")
    updated = update_skill(project, "lint", body="# Lint\n\nUpdated.", tags=["static"])
    assert updated is not None
    assert "static" in updated["tags"]
    full = get_skill(project, "lint")
    assert full and "Updated" in full["body"]
    assert delete_skill(project, "lint")
    assert list_skills(project) == []


def test_list_skills_filter_by_milestone(tmp_path: Path):
    project = tmp_path / "TEST-PROJ"
    project.mkdir()
    register_skill(project, name="M2 task", body="# M2", milestone_ids=["M2"])
    register_skill(project, name="M4 task", body="# M4", milestone_ids=["M4"])
    m2_only = list_skills(project, milestone="M2")
    assert len(m2_only) == 1
    assert m2_only[0]["name"] == "M2 task"