"""Item 4: interface vs module module_kind + DQL kind."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IF_FL = ROOT / "design" / "extras" / "sv_interface" / "filelist.f"


@pytest.mark.requires_engine
def test_interface_module_kind():
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(str(IF_FL))
    assert mods["bus_if"].module_kind == "interface"
    assert mods["top_if"].module_kind == "module"
    children = {e.child_module for e in mods["top_if"].instances}
    assert "bus_if" in children


@pytest.mark.requires_engine
def test_kind_dql(tmp_path):
    import sqlite3

    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import plan_dql

    db = tmp_path / "if.hch.db"
    build_index_from_filelist(str(IF_FL), str(db), top_module="top_if")
    plan = plan_dql('kind = "interface"')
    con = sqlite3.connect(db)
    names = {r[2] for r in con.execute(plan.sql, plan.params).fetchall()}
    con.close()
    assert "bus_if" in names