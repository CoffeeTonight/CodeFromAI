"""Phase 4: DQL subset → SQL."""

import sqlite3
from pathlib import Path

import pytest

from hch.paths import design_dir

DESIGN = design_dir("HDLforAST")
FILELIST = DESIGN / "filelist.f"


@pytest.mark.requires_engine
def test_dql_module_glob(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import plan_dql

    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "q.hch.db"
    store = build_index_from_filelist(str(FILELIST), str(db), top_module="top_module")
    store.close()

    plan = plan_dql('module ~ "middle*"')
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(plan.sql, plan.params).fetchall()
    conn.close()
    assert len(rows) >= 1
    assert any("middle" in r["module_name"] for r in rows)