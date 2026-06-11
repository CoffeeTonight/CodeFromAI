"""GUI clipboard + depth summary helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "unified_verify"


def _build_anchor_db(tmp_path: Path) -> Path:
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "gui_clip.hch.db"
    build_index_from_filelist(
        str(DESIGN / "filelist.f"),
        str(db),
        top_module="hc_verify_top",
        index_cwd=str(DESIGN),
        batch_size=64,
        depth_anchor_module_patterns=["*_top"],
        depth_anchor_extra=2,
        depth_shallow=2,
        blackbox_paths=["hfa"],
    ).close()
    return db


@pytest.mark.requires_engine
def test_format_subtree_clipboard_nested_anchor(tmp_path: Path):
    from hch.apps.gui.main_window import format_subtree_clipboard
    from hch.index.store import HierarchyStore

    store = HierarchyStore(str(_build_anchor_db(tmp_path)))
    try:
        text = format_subtree_clipboard(store.conn, "hc_verify_top.u_anchor_nested")
        assert "hc_verify_top.u_anchor_nested  (outer_top)" in text
        assert "hc_verify_top.u_anchor_nested.u_inner  (inner_top)" in text
        assert "hc_verify_top.u_anchor_nested.u_inner.u_chain.u_d2  (anchor_d2)" in text
        assert "u_d2.u_d3" not in text
        assert text.index("u_inner") < text.index("u_chain")
    finally:
        store.close()


@pytest.mark.requires_engine
def test_depth_summary_helpers(tmp_path: Path):
    from hch.apps.gui.main_window import (
        fetch_db_depth_stats,
        fetch_subtree_depth_stats,
        format_index_depth_summary,
        format_selection_depth_line,
    )
    from hch.index.store import HierarchyStore

    store = HierarchyStore(str(_build_anchor_db(tmp_path)))
    try:
        stats = fetch_db_depth_stats(store.conn)
        assert stats["count"] > 0
        assert stats["min_depth"] == 0
        assert stats["max_depth"] is not None and stats["max_depth"] >= 0

        summary = format_index_depth_summary(store.conn)
        assert "instances:" in summary
        assert "DB depth:" in summary
        assert "shallow: 2" in summary
        assert "anchor +2" in summary

        sub = fetch_subtree_depth_stats(
            store.conn, "hc_verify_top.u_anchor_nested"
        )
        assert sub is not None
        assert sub["count"] >= 3
        assert sub["relative_max"] >= 2

        sel_line = format_selection_depth_line(
            store.conn, "hc_verify_top.u_anchor_nested"
        )
        assert "selected: depth" in sel_line
        assert "subtree" in sel_line
    finally:
        store.close()