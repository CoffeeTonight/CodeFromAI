from __future__ import annotations

import json
from pathlib import Path

from soc_verify.node_guide import (
    NodeGuideEntry,
    list_node_guides,
    materialize_node_guide,
    materialize_all,
)
from soc_verify.node_guide_wizard import add_node_from_dict
from soc_verify.obsidian_md import wikilink


ROOT = Path(__file__).resolve().parents[1]


def test_materialize_node_writes_ast_vault_paths(tmp_path: Path):
    project = tmp_path / "projects" / "NG-SOC"
    project.mkdir(parents=True)
    (project / "state.yaml").write_text("current_milestone: M2\n", encoding="utf-8")

    entry = NodeGuideEntry(
        id="block_lint",
        milestone="M2",
        stage="static",
        group="lint_block",
        what_to_do="Run SpyGlass block lint after compile.",
        skill_body="# Block lint\n\nRun SpyGlass.",
        check_hints="PASS when 0 critical lint",
        requires=["c_compile"],
        refresh_events=["tag_refresh"],
        label_ko="Block lint",
    )
    result = materialize_node_guide(project, entry, root=ROOT)
    assert result["ok"]
    assert (project / "skills" / "block_lint" / "SKILL.md").is_file()
    assert (project / "knowledge" / "obsidian" / "03-nodes" / "block_lint.md").is_file()
    assert (
        project / "knowledge" / "obsidian" / "02-stages" / "static" / "groups" / "lint_block" / "CHECK.md"
    ).is_file()
    assert (project / "knowledge" / "obsidian" / "00-index" / "graph.json").is_file()
    assert (project / "knowledge" / "obsidian" / "00-index" / "PROJECT-MOC.md").is_file()
    assert (project / "knowledge" / "obsidian" / "01-milestones" / "M2" / "MOC.md").is_file()

    check = (project / "verification" / "static" / "lint_block" / "CHECK.md").read_text(encoding="utf-8")
    assert check.startswith("---")
    assert wikilink("00-index", "PROJECT-MOC") in check
    assert "`#gate/static/lint_block`" in check
    obs_check = (
        project
        / "knowledge"
        / "obsidian"
        / "02-stages"
        / "static"
        / "groups"
        / "lint_block"
        / "CHECK.md"
    ).read_text(encoding="utf-8")
    assert obs_check == check

    graph = json.loads(
        (project / "knowledge" / "obsidian" / "00-index" / "graph.json").read_text(encoding="utf-8")
    )
    assert graph["contract"] == "obsidian_ast_graph_v1"
    assert "block_lint" in graph["nodes"]
    assert graph["nodes"]["block_lint"]["gates"]["check"].endswith("lint_block/CHECK.md")

    manifest = (project / "verification" / "static" / "lint_block" / "manifest.yaml").read_text(
        encoding="utf-8"
    )
    assert "knowledge/obsidian/02-stages/static/groups/lint_block/CHECK.md" in manifest
    assert "knowledge/obsidian/03-nodes/block_lint.md" in manifest
    assert (project / "meta" / "pipeline_graphs" / "user_M2.yaml").is_file()
    assert len(list_node_guides(project)) == 1


def test_add_node_from_dict(tmp_path: Path):
    project = tmp_path / "projects" / "JSON-SOC"
    project.mkdir(parents=True)
    data = {
        "id": "smoke_sim",
        "milestone": "M3",
        "stage": "simulation",
        "group": "gpio_smoke",
        "what_to_do": "GPIO smoke sim",
        "requires": [],
    }
    out = add_node_from_dict(tmp_path, "JSON-SOC", data)
    assert out["ok"]
    assert (project / "verification" / "simulation" / "gpio_smoke" / "CHECK.md").is_file()
    assert (project / "knowledge" / "obsidian" / "03-nodes" / "smoke_sim.md").is_file()


def test_materialize_all_idempotent(tmp_path: Path):
    project = tmp_path / "projects" / "ALL-SOC"
    project.mkdir(parents=True)
    entry = NodeGuideEntry(
        id="sanity_x",
        milestone="M2",
        stage="sanity",
        group="sanity_x",
        what_to_do="Quick compile check",
    )
    materialize_node_guide(project, entry, root=ROOT)
    results = materialize_all(project, root=ROOT)
    assert len(results) == 1