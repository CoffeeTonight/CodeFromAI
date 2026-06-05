"""Phase 2: filelist → module graph."""

from pathlib import Path

import pytest

from hch.paths import design_dir

DESIGN = design_dir("HDLforAST")
FILELIST = DESIGN / "filelist.f"


@pytest.mark.requires_engine
def test_filelist_ingest_modules():
    from hch.ingest.ingest import ingest_filelist

    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    mods = ingest_filelist(FILELIST)
    assert "top_module" in mods
    assert "middle_module" in mods
    assert len(mods["top_module"].ports) >= 5