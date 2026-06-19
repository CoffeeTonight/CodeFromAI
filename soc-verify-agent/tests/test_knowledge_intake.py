from __future__ import annotations

import json
from pathlib import Path

from soc_verify.knowledge_intake import (
    add_source_interactive,
    collect_knowledge_bundle,
    list_verification_gates,
    normalize_to_obsidian,
    seed_sources_from_discovered,
)


ROOT = Path(__file__).resolve().parents[1]


def test_list_verification_gates_example():
    gates = list_verification_gates(ROOT / "projects" / "EXAMPLE-SOC")
    assert any(g.get("group") == "gpio_ext" for g in gates)


def test_collect_and_normalize_stub(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "P1"
    (project / "verification" / "sanity" / "g1").mkdir(parents=True)
    (project / "verification" / "sanity" / "g1" / "manifest.yaml").write_text(
        "stage: sanity\ngroup: g1\nmilestone: M1\n",
        encoding="utf-8",
    )
    (project / "discovered.yaml").write_text(
        "project_id: P1\ngit_url: git@test\nschedule_plan: soc-dv-4p-v1\ncurrent_milestone: M2\n",
        encoding="utf-8",
    )
    (root / "registry").mkdir()
    spec_src = ROOT / "registry" / "knowledge_intake_spec.yaml"
    if spec_src.is_file():
        (root / "registry" / "knowledge_intake_spec.yaml").write_text(
            spec_src.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    tpl_dir = root / "templates" / "obsidian" / "projects"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "_PROJECT_TEMPLATE.md").write_text(
        (ROOT / "templates" / "obsidian" / "projects" / "_PROJECT_TEMPLATE.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "config.json").write_text(json.dumps({"llm": {"mode": "stub"}, "paths": {}}), encoding="utf-8")

    add_source_interactive(project, source_type="markdown", location="docs/spec.md", root=root)
    (project / "docs").mkdir(parents=True)
    (project / "docs" / "spec.md").write_text("# Spec\nGPIO verification overview.\n", encoding="utf-8")

    bundle = collect_knowledge_bundle(root, "P1")
    assert len(bundle.get("sources", [])) >= 2
    intake_moc = project / "knowledge" / "obsidian" / "05-intake" / "SOURCES-MOC.md"
    assert intake_moc.is_file()
    assert "[[05-intake/sources/" in intake_moc.read_text(encoding="utf-8")
    assert (project / "knowledge" / "obsidian" / "05-intake" / "intake.json").is_file()

    result = normalize_to_obsidian(root, "P1")
    assert result.get("ok")
    note = root / "templates" / "obsidian" / "projects" / "P1.md"
    assert note.is_file()
    assert "P1" in note.read_text(encoding="utf-8")
    assert "PASS" in intake_moc.read_text(encoding="utf-8") or "정규화" in intake_moc.read_text(encoding="utf-8")


def test_seed_from_discovered(tmp_path: Path):
    project = tmp_path / "projects" / "PX"
    project.mkdir(parents=True)
    (project / "discovered.yaml").write_text(
        "confluence_page_id: '123'\ndoc_path: docs/verify.md\n",
        encoding="utf-8",
    )
    data = seed_sources_from_discovered(project)
    types = [s.get("type") for s in data.get("sources") or []]
    assert "confluence" in types