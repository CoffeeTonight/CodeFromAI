"""instances.module_ref column + macro hierarchy meta."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DUP = ROOT / "design" / "extras" / "multi_def_dup"
MACRO = ROOT / "design" / "extras" / "macro_hierarchy"


@pytest.mark.skipif(not (DUP / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_instance_module_ref_column_multi_def(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore
    from hch.query.dql.sql_compiler import plan_dql

    db = tmp_path / "dup_inst_ref.hch.db"
    store = build_index_from_filelist(
        str(DUP / "filelist.f"),
        str(db),
        top_module="top_dup",
        index_cwd=DUP,
    )
    rows = store.conn.execute(
        """
        SELECT i.inst_leaf_name, i.module_ref
        FROM instances i
        WHERE i.module_ref IS NOT NULL AND i.module_ref != ''
        """
    ).fetchall()
    mod_rows = store.conn.execute(
        "SELECT module_ref FROM modules WHERE module_name='dup'"
    ).fetchall()
    store.close()
    assert len(mod_rows) >= 2
    by_leaf = {r[0]: r[1] for r in rows if r[0].startswith("u_")}
    assert "u_dup" in by_leaf and "u_dup2" in by_leaf
    assert "dup_a.v" in by_leaf["u_dup"]
    assert "dup_b.v" in by_leaf["u_dup2"]

    import sqlite3

    store2 = HierarchyStore(str(db))
    plan = plan_dql('module_ref ~ "*dup_a.v*"')
    store2.conn.row_factory = sqlite3.Row
    hits = store2.conn.execute(plan.sql, plan.params).fetchall()
    store2.close()
    assert len(hits) >= 1


@pytest.mark.skipif(not (MACRO / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_macro_hierarchy_index_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    db = tmp_path / "macro.hch.db"
    store = build_index_from_filelist(
        str(MACRO / "filelist.f"),
        str(db),
        top_module="top_macro",
        index_cwd=MACRO,
    )
    macro_n = int(store.get_meta("macro_instance_count", "0"))
    paths = {r.full_path for r in store.load_flat_instances()}
    store.close()
    assert macro_n >= 2
    assert any("u_x" in p for p in paths)
    assert any("u_y" in p for p in paths)