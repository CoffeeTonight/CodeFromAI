"""Web subtree API matches GUI hierarchy text."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "unified_verify"


@pytest.mark.requires_engine
def test_web_subtree_api_nested_anchor(tmp_path: Path):
    from hch.apps.api.db_service import HierarchyDbService
    from hch.apps.hierarchy_view import format_subtree_text
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "web_sub.hch.db"
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

    svc = HierarchyDbService(str(db))
    try:
        meta = svc.meta()
        assert "anchor +2" in meta["depth_summary"]
        assert meta["db_max_depth"] is not None

        path = "hc_verify_top.u_anchor_nested"
        view = svc.subtree_view(path)
        assert view is not None
        assert view["text"] == format_subtree_text(svc.conn, path)
        assert "u_d2.u_d3" not in view["text"]
        assert view["stats"]["relative_max"] >= 2
    finally:
        svc.close()