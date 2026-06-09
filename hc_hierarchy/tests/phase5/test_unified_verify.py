"""Unified verification SoC — all design/extras features in one corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "unified_verify"


@pytest.mark.requires_engine
def test_unified_verify_index_and_dql(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import apply_post_filters, plan_dql

    db = tmp_path / "unified.hch.db"
    store = build_index_from_filelist(
        str(DESIGN / "filelist.f"),
        str(db),
        top_module="hc_verify_top",
        index_cwd=DESIGN,
    )
    fl_errors = json.loads(store.get_meta("filelist_errors", "[]"))
    assert len(fl_errors) >= 6
    assert any("ghost_soc.v" in e for e in fl_errors)
    assert any("mid_module.v" in e for e in fl_errors)
    assert any("test_top.v" in e for e in fl_errors)
    assert any("uvm.f" in e for e in fl_errors)

    paths = {r[0] for r in store.conn.execute("SELECT full_path FROM instances")}
    store.close()
    assert "hc_verify_top.u_gen_soc.gen_blk.gen_loop[0].u_cell" in paths
    assert "hc_verify_top.u_arr.b[1].c[0]" in paths
    assert "hc_verify_top.u_bind_wrap.u_sub.u_bind_hier" in paths
    assert "hc_verify_top.u_ghost" in paths
    assert any("u_x" in p for p in paths)

    checks = [
        'expand_ports AND port_path = "hc_verify_top.u_arr.b[1].c[0].int[6][1:0]"',
        'path = "hc_verify_top.u_gen_soc.u_alt"',
        'from_macro = "1"',
        'child_kind = "unresolved" AND path = "hc_verify_top.u_ghost"',
    ]
    for q in checks:
        plan = plan_dql(q)
        conn = __import__("sqlite3").connect(db)
        conn.row_factory = __import__("sqlite3").Row
        rows = apply_post_filters(
            [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()],
            plan,
        )
        conn.close()
        assert rows, q