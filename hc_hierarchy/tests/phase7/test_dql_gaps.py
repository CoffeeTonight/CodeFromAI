"""DQL gaps: parent, expand_ports, array instance names."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mini_db(tmp_path: Path) -> Path:
    db = tmp_path / "gaps.hch.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE modules (id INTEGER PRIMARY KEY, module_name TEXT, module_kind TEXT DEFAULT 'module',
            module_ref TEXT UNIQUE, definition_file_id INTEGER DEFAULT 1, port_json TEXT, param_json TEXT, inst_json TEXT);
        CREATE TABLE files (id INTEGER PRIMARY KEY, filepath TEXT);
        INSERT INTO files VALUES (1, 't.v');
        INSERT INTO modules VALUES (1, 'top', 'module', 't.v::top', 1, '["clk","rst_n"]', '{}', '[]');
        CREATE TABLE instances (
            id INTEGER PRIMARY KEY, full_path TEXT UNIQUE, inst_leaf_name TEXT,
            module_id INTEGER, depth INTEGER, parent_path TEXT, filepath_id INTEGER,
            port_json TEXT, param_json TEXT);
        INSERT INTO instances VALUES
            (1, 'top', 'top', 1, 0, NULL, 1, '["clk","rst_n"]', '{}'),
            (2, 'top.u_a', 'u_a', 1, 1, 'top', 1, '["irq"]', '{}');
        """
    )
    con.commit()
    con.close()
    return db


def test_parent_field(tmp_path):
    from hch.query.dql.planner import apply_post_filters, plan_dql

    db = _mini_db(tmp_path)
    plan = plan_dql('parent = "top"')
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = apply_post_filters(
        [dict(r) for r in con.execute(plan.sql, plan.params).fetchall()], plan
    )
    con.close()
    assert len(rows) == 1
    assert rows[0]["full_path"] == "top.u_a"


def test_expand_ports(tmp_path):
    from hch.query.dql.planner import apply_post_filters, plan_dql

    db = _mini_db(tmp_path)
    plan = plan_dql('path ^= "top" AND expand_ports')
    assert plan.post_filter_expand_ports
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = apply_post_filters(
        [dict(r) for r in con.execute(plan.sql, plan.params).fetchall()], plan
    )
    con.close()
    port_paths = {r["port_path"] for r in rows}
    assert "top.clk" in port_paths
    assert "top.u_a.irq" in port_paths


@pytest.mark.requires_engine
def test_array_instance_names_extracted():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    p = Path("/tmp/hch_arr_edges.v")
    p.write_text(
        "module leaf(input c); endmodule\nmodule top; leaf u[0:1](); endmodule\n",
        encoding="utf-8",
    )
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    names = {e.inst_name for e in mods["top"].instances}
    assert names == {"u[0]", "u[1]"}


@pytest.mark.requires_engine
def test_hdlforast_ifdef_variant():
    from hch.ingest.ifdef_variant import compare_instance_sets, instance_set_under_top
    from hch.ingest.ingest import ingest_source_files
    from hch.paths import design_dir

    top = design_dir("HDLforAST") / "top_module.v"
    if not top.exists():
        pytest.skip("HDLforAST missing")
    base = ingest_source_files([top], include_dirs=[str(design_dir("HDLforAST"))])
    m1 = ingest_source_files(
        [top], include_dirs=[str(design_dir("HDLforAST"))], defines={"USE_M1": "1"}
    )
    diff = compare_instance_sets(
        instance_set_under_top(base, "top_module"),
        instance_set_under_top(m1, "top_module"),
    )
    assert diff["only_left"] != diff["only_right"]