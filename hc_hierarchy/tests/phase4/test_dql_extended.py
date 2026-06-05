"""DQL: OR, path ^=, port index via instance_ports."""

import sqlite3
import time

import pytest

from hch.paths import design_dir

FILELIST = design_dir("HDLforAST") / "filelist.f"


@pytest.fixture(scope="module")
def indexed_db(tmp_path_factory):
    from hch.index.loader import build_index_from_filelist

    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")
    db = tmp_path_factory.mktemp("dql_ext") / "ext.hch.db"
    store = build_index_from_filelist(str(FILELIST), str(db), top_module="top_module")
    store.close()
    return db


def _rows(db, query: str):
    from hch.query.dql.planner import apply_post_filters, plan_dql

    plan = plan_dql(query)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    out = [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()]
    conn.close()
    out = apply_post_filters(out, plan)
    return out


@pytest.mark.requires_engine
def test_path_prefix_caret(indexed_db):
    rows = _rows(indexed_db, 'path ^= "top_module.u_middle"')
    assert rows
    assert all(r["full_path"].startswith("top_module.u_middle") for r in rows)


@pytest.mark.requires_engine
def test_or_modules(indexed_db):
    rows = _rows(
        indexed_db,
        '(module ~ "middle*" OR module ~ "sub_*")',
    )
    mods = {r["module_name"] for r in rows}
    assert mods & {"middle_module", "sub_module"}


@pytest.mark.requires_engine
def test_port_index_clk(indexed_db):
    rows = _rows(indexed_db, 'port ~ "clk" AND path ^= "top_module"')
    assert rows
    for r in rows:
        ports = __import__("json").loads(r["port_json"] or "[]")
        assert any("clk" in p for p in ports)


@pytest.mark.requires_engine
def test_query_latency_under_200ms(indexed_db):
    """Indexed lookup should stay fast at HDLforAST scale (<<10k rows)."""
    from hch.query.dql.planner import plan_dql

    queries = [
        'path ^= "top_module"',
        'module ~ "middle*"',
        'port ~ "clk"',
        '(module ~ "uart*" OR module ~ "sub_*") AND path ^= "top"',
    ]
    t0 = time.perf_counter()
    for q in queries:
        plan = plan_dql(q)
        conn = sqlite3.connect(indexed_db)
        conn.execute(plan.sql, plan.params).fetchall()
        conn.close()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 200, f"4 queries took {elapsed_ms:.1f}ms"