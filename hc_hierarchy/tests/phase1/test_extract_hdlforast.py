"""Phase 1: extract modules + structural hierarchy (unified_verify hfa)."""

import pytest

from hch.engine.availability import check_engine

from hch.paths import unified_filelist, unified_verify_dir


@pytest.mark.requires_engine
def test_filelist_ingest_and_hierarchy():
    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not unified_filelist().exists():
        pytest.skip(f"filelist missing: {unified_filelist()}")

    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.ingest import ingest_filelist

    all_modules = ingest_filelist(unified_filelist(), index_cwd=str(unified_verify_dir()))

    assert "top_module" in all_modules
    flat = elaborate_flat(all_modules, top_module="top_module")
    paths = [f.full_path for f in flat]
    assert any("top_module" in p for p in paths)
    # Expect at least one child under top
    assert any(p.count(".") >= 1 for p in paths), f"hierarchy paths: {paths}"