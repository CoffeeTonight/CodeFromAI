"""Phase 1b: preprocessor defines change instance names."""

from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir

TOP = hfa_rtl_dir() / "top_module.v"


@pytest.mark.requires_engine
def test_define_changes_instance_name():
    from hch.ingest.ingest import ingest_source_files

    if not TOP.exists():
        pytest.skip(f"missing {TOP}")

    base = ingest_source_files([TOP], include_dirs=[str(hfa_rtl_dir())])
    m1 = ingest_source_files([TOP], include_dirs=[str(hfa_rtl_dir())], defines={"USE_M1": "1"})
    assert "top_module" in base and "top_module" in m1
    names_base = {e.inst_name for e in base["top_module"].instances}
    names_m1 = {e.inst_name for e in m1["top_module"].instances}
    assert "u_middle_1" in names_m1 or "u_middle_1" in str(names_m1)
    assert names_base != names_m1