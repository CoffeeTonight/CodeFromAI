"""Web help payload and API."""

from __future__ import annotations

from hch.apps.help_text import web_dql_example_groups, web_help_payload


def test_web_help_payload_structure():
    payload = web_help_payload()
    assert payload["version"] == "1"
    assert "inst_vs_path" in payload
    assert any(s["id"] == "examples" for s in payload["sections"])
    groups = web_dql_example_groups()
    path_group = next(g for g in groups if g["id"] == "path")
    queries = [e["query"] for e in path_group["examples"]]
    assert any("*t*.*" in q for q in queries)
    assert any("{{TOP}}" in q for q in queries)