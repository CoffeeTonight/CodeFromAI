from __future__ import annotations

import json

from soc_verify.obsidian_md import (
    build_graph_ast,
    build_intake_ast,
    obsidian_paths,
    obsidian_relpaths,
    render_check_note,
    render_node_hub_note,
    wikilink,
)


def test_obsidian_check_has_frontmatter_and_ast_wikilinks():
    entry = {
        "id": "lint_x",
        "stage": "static",
        "group": "lint_x",
        "milestone": "M2",
        "what_to_do": "Run lint",
        "check_hints": "0 errors",
    }
    md = render_check_note("PROJ", entry)
    assert md.startswith("---")
    assert "type: gate_check" in md
    assert "ast_layer: 02-stages" in md
    assert wikilink("00-index", "PROJECT-MOC") in md
    assert wikilink("03-nodes", "lint_x") in md


def test_node_hub_links_ast_gate_paths():
    entry = {
        "id": "n1",
        "stage": "sanity",
        "group": "g1",
        "milestone": "M2",
        "what_to_do": "smoke",
        "requires": ["prev"],
    }
    md = render_node_hub_note("PROJ", entry)
    assert wikilink("02-stages", "sanity", "groups", "g1", "CHECK") in md
    assert wikilink("04-skills", "n1") in md
    assert "`#node/n1`" in md


def test_obsidian_relpaths_ast_layers():
    entry = {"id": "blk", "stage": "static", "group": "lint", "milestone": "M2"}
    rel = obsidian_relpaths(entry)
    assert rel["node_hub"] == "03-nodes/blk.md"
    assert rel["check"] == "02-stages/static/groups/lint/CHECK.md"
    assert rel["skill"] == "04-skills/blk.md"
    assert rel["graph_json"] == "00-index/graph.json"


def test_obsidian_paths_include_project_prefix():
    entry = {"id": "blk", "stage": "static", "group": "lint", "milestone": "M2"}
    paths = obsidian_paths("SOC", entry)
    assert paths["node_hub"] == "projects/SOC/knowledge/obsidian/03-nodes/blk.md"


def test_build_graph_ast_edges_and_layers():
    entries = [
        {
            "id": "a",
            "stage": "sanity",
            "group": "g1",
            "milestone": "M2",
            "requires": [],
        },
        {
            "id": "b",
            "stage": "static",
            "group": "g2",
            "milestone": "M2",
            "requires": ["a"],
        },
    ]
    ast = build_graph_ast("SOC", entries)
    assert ast["contract"] == "obsidian_ast_graph_v1"
    assert ast["layers"]["nodes"] == "03-nodes"
    assert "a" in ast["nodes"]
    assert ast["nodes"]["b"]["gates"]["check"] == "02-stages/static/groups/g2/CHECK.md"
    assert {"from": "a", "to": "b", "type": "requires"} in ast["edges"]
    json.dumps(ast)


def test_build_intake_ast_runtime_mirror():
    bundle = {
        "project_id": "SOC",
        "collected_at": "2026-06-18T00:00:00+00:00",
        "sources": [
            {"type": "discovered", "label": "discovered.yaml", "ok": True, "content": "{}"},
            {"type": "markdown", "label": "spec", "ok": True, "content": "# Spec"},
        ],
    }
    ast = build_intake_ast("SOC", bundle)
    assert ast["contract"] == "obsidian_intake_v1"
    assert ast["runtime_dir"] == "intake"
    assert ast["runtime_artifacts"]["bundle"] == "intake/knowledge_bundle.json"
    assert len(ast["sources"]) == 2
    assert ast["sources"][0]["note"].startswith("05-intake/sources/")


def test_graph_ast_includes_intake_layer():
    intake = {"moc": "05-intake/SOURCES-MOC.md", "source_count": 1, "sources": []}
    ast = build_graph_ast("SOC", [], intake=intake)
    assert ast["layers"]["intake"] == "05-intake"
    assert ast["intake"]["moc"] == "05-intake/SOURCES-MOC.md"