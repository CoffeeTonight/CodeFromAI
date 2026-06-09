"""DQL inst / file / text export."""

import sqlite3

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

FILELIST = unified_filelist()


@pytest.fixture(scope="module")
def indexed_db(tmp_path_factory):
    from hch.index.loader import build_index_from_filelist

    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")
    db = tmp_path_factory.mktemp("dql_inst") / "inst.hch.db"
    store = build_index_from_filelist(str(FILELIST), str(db), top_module="top_module", index_cwd=str(unified_verify_dir()))
    store.close()
    return db


def _rows(db, query: str):
    from hch.query.dql.planner import plan_dql

    plan = plan_dql(query)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    out = [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()]
    conn.close()
    return out


@pytest.mark.requires_engine
def test_inst_glob_matches_leaf(indexed_db):
    rows = _rows(indexed_db, 'inst ~ "u_middle*"')
    assert rows
    assert all("u_middle" in r["inst_leaf_name"] for r in rows)
    assert all("top_module" in r["full_path"] for r in rows)


@pytest.mark.requires_engine
def test_module_vs_inst(indexed_db):
    by_mod = _rows(indexed_db, 'module ~ "middle*"')
    by_inst = _rows(indexed_db, 'inst ~ "u_middle_0"')
    assert by_mod
    assert by_inst
    assert by_inst[0]["inst_leaf_name"] == "u_middle_0"
    assert by_mod[0]["module_name"] == "middle_module"


@pytest.mark.requires_engine
def test_format_rows_text():
    from hch.query.dql.results import format_rows_text

    text = format_rows_text(
        [
            {
                "full_path": "top.u_a",
                "inst_leaf_name": "u_a",
                "module_name": "foo",
                "filepath": "/rtl/foo.v",
                "depth": 1,
                "port_json": '["clk"]',
            }
        ],
        query='inst ~ "u_a"',
    )
    assert "# inst ~" in text
    assert "full_path\tinst\tmodule" in text
    assert "top.u_a\tu_a\tfoo" in text