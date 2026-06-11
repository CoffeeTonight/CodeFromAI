"""unified_verify: depth-anchor-module + anchor_extra on *_top chains."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "unified_verify"
FILELIST = DESIGN / "filelist.f"
TOP = "hc_verify_top"

# Suffix *_top matches outer_top/inner_top/flat_top/defparam_top, not hc_verify_top.
ANCHOR_MODULE = ["*_top"]
ANCHOR_EXTRA = 2


def _index(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    db = tmp_path / "unified_anchor.hch.db"
    build_index_from_filelist(
        str(FILELIST),
        str(db),
        top_module=TOP,
        index_cwd=str(DESIGN),
        batch_size=64,
        depth_anchor_module_patterns=ANCHOR_MODULE,
        depth_anchor_extra=ANCHOR_EXTRA,
        depth_shallow=2,
        skim_parse=True,
        blackbox_paths=["hfa"],
    ).close()
    store = HierarchyStore(str(db))
    return store


@pytest.mark.requires_engine
def test_flat_top_anchor_extra_two_levels(tmp_path: Path):
    store = _index(tmp_path)
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        base = f"{TOP}.u_anchor_flat.u_chain"
        assert f"{TOP}.u_anchor_flat" in paths
        assert f"{base}" in paths
        assert f"{base}.u_d2" in paths
        assert f"{base}.u_d2.u_d3" not in paths
        assert f"{base}.u_d2.u_d3.u_l" not in paths
    finally:
        store.close()


@pytest.mark.requires_engine
def test_nested_top_resets_anchor_extra_at_inner(tmp_path: Path):
    """outer_top then inner_top within 1 hop — +2 from inner_top only, not cumulative."""
    store = _index(tmp_path)
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        inner = f"{TOP}.u_anchor_nested.u_inner.u_chain"
        assert f"{TOP}.u_anchor_nested" in paths
        assert f"{TOP}.u_anchor_nested.u_inner" in paths
        assert inner in paths
        assert f"{inner}.u_d2" in paths
        assert f"{inner}.u_d2.u_d3" not in paths
        # Would exist if extra stacked from outer_top (+2) then again from inner (+2)
        assert f"{inner}.u_d2.u_d3.u_l" not in paths
    finally:
        store.close()


@pytest.mark.requires_engine
def test_anchor_meta_recorded(tmp_path: Path):
    store = _index(tmp_path)
    try:
        assert store.get_meta("depth_anchor_extra") == str(ANCHOR_EXTRA)
        import json

        mods = json.loads(store.get_meta("depth_anchor_module_json") or "[]")
        assert "*_top" in mods
    finally:
        store.close()