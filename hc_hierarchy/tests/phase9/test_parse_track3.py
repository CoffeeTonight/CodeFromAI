"""Track 3: parametric instance signatures (same cell, different #())."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOP = ROOT / "design" / "extras" / "parse_track3" / "rtl" / "top_param.v"


@pytest.mark.requires_engine
def test_parametric_instances_not_merged():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees
    from hch.ingest.parse_tags import param_signature

    trees = parse_syntax_trees([TOP])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(TOP))}
    edges = mods["top_param"].instances
    sigs = {param_signature(e.param_overrides) for e in edges if e.child_module == "child"}
    assert len(sigs) >= 2


@pytest.mark.requires_engine
def test_flatten_keeps_both_param_children(tmp_path):
    from hch.index.loader import build_index_from_filelist

    fl = ROOT / "design" / "extras" / "parse_track3" / "filelist.f"
    db = tmp_path / "t3.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="top_param")
    paths = {
        r[0]
        for r in store.conn.execute(
            "SELECT full_path FROM instances WHERE full_path LIKE '%.u_%'"
        ).fetchall()
    }
    store.close()
    assert "top_param.u_a" in paths
    assert "top_param.u_b" in paths