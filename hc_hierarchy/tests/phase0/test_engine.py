"""Phase 0: engine availability and optional live parse."""

from pathlib import Path

import pytest

from hch.engine.availability import check_engine

from hch.paths import hfa_rtl_dir

SAMPLE = hfa_rtl_dir() / "top_module.v"


def test_parse_engine_available():
    status = check_engine()
    assert status.available, f"{status.message} ({status.error})"
    assert status.backend == "pyslang"


@pytest.mark.requires_engine
def test_engine_parse_top_module():
    status = check_engine()
    if not status.available:
        pytest.skip(status.message)

    if not SAMPLE.exists():
        pytest.skip(f"sample missing: {SAMPLE}")

    from hch.ingest.ingest import ingest_source_files

    mods = ingest_source_files([SAMPLE], include_dirs=[str(hfa_rtl_dir())])
    names = set(mods.keys())
    assert "top_module" in names
    top = mods["top_module"]
    assert len(top.ports) >= 1