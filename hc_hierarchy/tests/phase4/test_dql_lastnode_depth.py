"""DQL lastnode modifier and depth field."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _mini_db(tmp_path: Path) -> Path:
    db = tmp_path / "mini.hch.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE modules (id INTEGER PRIMARY KEY, module_name TEXT);
        CREATE TABLE files (id INTEGER PRIMARY KEY, filepath TEXT);
        CREATE TABLE instances (
            id INTEGER PRIMARY KEY,
            full_path TEXT UNIQUE,
            inst_leaf_name TEXT,
            module_id INTEGER,
            filepath_id INTEGER,
            depth INTEGER,
            parent_path TEXT,
            port_json TEXT
        );
        INSERT INTO modules VALUES (1, 'top'), (2, 'child');
        INSERT INTO files VALUES (1, 'top.v');
        INSERT INTO instances VALUES
            (1, 'top', 'top', 1, 1, 0, NULL, NULL),
            (2, 'top.u_a', 'u_a', 2, 1, 1, 'top', NULL),
            (3, 'top.u_a.u_b', 'u_b', 2, 1, 2, 'top.u_a', NULL);
        """
    )
    con.commit()
    con.close()
    return db


def _run(db: Path, query: str) -> list:
    from hch.query.dql.planner import apply_post_filters, plan_dql

    plan = plan_dql(query)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(plan.sql, plan.params).fetchall()]
    con.close()
    return apply_post_filters(rows, plan)


def test_depth_eq(tmp_path):
    db = _mini_db(tmp_path)
    rows = _run(db, 'path ^= "top" AND depth == 1')
    assert len(rows) == 1
    assert rows[0]["full_path"] == "top.u_a"


def test_depth_ge(tmp_path):
    db = _mini_db(tmp_path)
    rows = _run(db, "depth >= 2")
    assert {r["full_path"] for r in rows} == {"top.u_a.u_b"}


def test_lastnode(tmp_path):
    db = _mini_db(tmp_path)
    rows = _run(db, 'path ^= "top" AND lastnode')
    paths = {r["full_path"] for r in rows}
    assert paths == {"top.u_a.u_b"}


def test_node_count_dots(tmp_path):
    db = _mini_db(tmp_path)
    rows = _run(db, "node_count == 0")
    assert {r["full_path"] for r in rows} == {"top"}
    rows = _run(db, "node_count == 1")
    assert {r["full_path"] for r in rows} == {"top.u_a"}
    rows = _run(db, 'path ^= "top" AND node_count >= 2')
    assert {r["full_path"] for r in rows} == {"top.u_a.u_b"}


def test_plan_flags(tmp_path):
    from hch.query.dql.planner import plan_dql

    p = plan_dql('lastnode AND depth == 1')
    assert p.post_filter_lastnode is True
    assert "i.depth = ?" in p.sql

    p2 = plan_dql('node_count == 1 AND module ~ "top*"')
    assert p2.post_filter_lastnode is False
    assert "REPLACE(i.full_path" in p2.sql