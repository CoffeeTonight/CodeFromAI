"""Phase 1: extract modules + structural hierarchy from HDLforAST."""

from pathlib import Path

import pytest

from hch.engine.availability import check_engine

from hch.paths import design_dir

DESIGN = design_dir("HDLforAST")
FILELIST = DESIGN / "filelist.f"


@pytest.mark.requires_engine
def test_filelist_ingest_and_hierarchy():
    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not FILELIST.exists():
        pytest.skip(f"filelist missing: {FILELIST}")

    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.ingest import ingest_filelist

    all_modules = ingest_filelist(FILELIST)

    assert "top_module" in all_modules
    flat = elaborate_flat(all_modules, top_module="top_module")
    paths = [f.full_path for f in flat]
    assert any("top_module" in p for p in paths)
    # Expect at least one child under top
    assert any(p.count(".") >= 1 for p in paths), f"hierarchy paths: {paths}"