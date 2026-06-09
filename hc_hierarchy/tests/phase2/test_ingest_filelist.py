"""Phase 2: filelist → module graph."""

from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

FILELIST = unified_filelist()


@pytest.mark.requires_engine
def test_filelist_ingest_modules():
    from hch.ingest.ingest import ingest_filelist

    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    mods = ingest_filelist(FILELIST, index_cwd=str(unified_verify_dir()))
    assert "top_module" in mods
    assert "middle_module" in mods
    assert len(mods["top_module"].ports) >= 5