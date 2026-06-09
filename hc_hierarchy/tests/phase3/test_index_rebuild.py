"""Re-index must replace instances (no stale roots from prior --top)."""

from pathlib import Path

import pytest

from hch.paths import design_dir

FILELIST = design_dir("HDLforAST") / "filelist.f"


@pytest.mark.requires_engine
def test_reindex_with_top_clears_old_roots(tmp_path):
    from hch.engine.availability import check_engine
    from hch.index.loader import build_index_from_filelist

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "mix.hch.db"
    store = build_index_from_filelist(str(FILELIST), str(db), index_cwd=str(FILELIST.parent))
    all_paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert "test_module" in all_paths
    assert "top_module" in all_paths

    store = build_index_from_filelist(
        str(FILELIST),
        str(db),
        top_module="top_module",
        index_cwd=str(FILELIST.parent),
    )
    paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert "top_module" in paths
    assert "test_module" not in paths
    assert "top_a" not in paths
    assert "top_module.u_middle_0.u_subTop_0" in paths