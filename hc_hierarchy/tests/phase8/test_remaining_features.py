"""REMAINING.md items: port_path, wide OR limit, index meta."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "r.hch.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE modules (id INTEGER PRIMARY KEY, module_name TEXT, module_kind TEXT DEFAULT 'module',
            module_ref TEXT UNIQUE, definition_file_id INTEGER DEFAULT 1, port_json TEXT, param_json TEXT, inst_json TEXT);
        CREATE TABLE files (id INTEGER PRIMARY KEY, filepath TEXT);
        INSERT INTO files VALUES (1, 't.v');
        INSERT INTO modules VALUES (1, 'top', 'module', 't::top', 1, '[]', '{}', '[]');
        CREATE TABLE instances (
            id INTEGER PRIMARY KEY, full_path TEXT UNIQUE, inst_leaf_name TEXT,
            module_id INTEGER, depth INTEGER, parent_path TEXT, filepath_id INTEGER,
            port_json TEXT, param_json TEXT);
        CREATE TABLE instance_ports (id INTEGER PRIMARY KEY, instance_id INTEGER, port_name TEXT UNIQUE);
        INSERT INTO instances VALUES (1, 'top', 'top', 1, 0, NULL, 1, '["clk"]', '{}');
        INSERT INTO instance_ports VALUES (1, 1, 'clk');
        INSERT INTO instances VALUES (2, 'top.u_a', 'u_a', 1, 1, 'top', 1, '["irq"]', '{}');
        INSERT INTO instance_ports VALUES (2, 2, 'irq');
        """
    )
    con.commit()
    con.close()
    return db


def test_port_path_filter(tmp_path):
    from hch.query.dql.planner import apply_post_filters, plan_dql

    db = _db(tmp_path)
    plan = plan_dql('port_path = "top.clk"')
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = apply_post_filters(
        [dict(r) for r in con.execute(plan.sql, plan.params).fetchall()], plan
    )
    con.close()
    assert len(rows) == 1
    assert rows[0]["full_path"] == "top"


def test_wide_or_has_limit(tmp_path):
    from hch.query.dql.planner import plan_dql

    q = " OR ".join(f'path ^= "top.u_{i}"' for i in range(6))
    plan = plan_dql(q)
    assert plan.row_limit == 8000
    assert "LIMIT ?" in plan.sql


@pytest.mark.requires_engine
@pytest.mark.slow
def test_quick_elab_index_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    fl = Path(__file__).resolve().parents[2] / "design" / "extras" / "gen_ifdef_generate" / "filelist.f"
    if not fl.exists():
        pytest.skip("fixture missing")
    db = tmp_path / "elab.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="top_soc", elaborate=True)
    assert store.get_meta("elab_succeeded") == "1"
    assert int(store.get_meta("instance_count", "0")) >= 4
    store.close()