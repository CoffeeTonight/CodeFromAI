"""Phase 3: SQLite index build and SQL query."""

from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

FILELIST = unified_filelist()


@pytest.mark.requires_engine
def test_build_index_and_count(tmp_path):
    from hch.index.loader import build_index_from_filelist

    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "test.hch.db"
    store = build_index_from_filelist(str(FILELIST), str(db), top_module="top_module", index_cwd=str(unified_verify_dir()))
    n = store.count_instances()
    store.close()
    assert n >= 2
    assert db.exists()