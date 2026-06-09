"""Verify hierarchy, instance, ports, and file are populated via pyslang (hc_hierarchy only)."""

from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

FILELIST = unified_filelist()


@pytest.mark.requires_engine
def test_index_has_hierarchy_ports_and_file(tmp_path):
    from hch.engine.availability import check_engine
    from hch.index.loader import build_index_from_filelist

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "hdl.hch.db"
    store = build_index_from_filelist(str(FILELIST), str(db), top_module="top_module", index_cwd=str(unified_verify_dir()))
    rows = store.export_instance_dicts()
    store.close()

    assert len(rows) >= 2
    by_name = {r["name"]: r for r in rows}
    assert any("top_module" in n for n in by_name)

    child = next(
        (r for n, r in by_name.items() if n.startswith("top_module.") and "." in n),
        None,
    )
    assert child is not None, f"expected child under top_module, got {list(by_name)[:8]}"
    assert child["module"]
    assert child["file"], "definition file should be set"
    assert isinstance(child["ports"], list)

    mid_path = next(
        (n for n in by_name if "u_middle" in n and by_name[n]["module"] == "middle_module"),
        None,
    )
    if mid_path:
        mid = by_name[mid_path]
        assert set(mid["ports"]) >= {"clk", "reset", "out"}, mid["ports"]