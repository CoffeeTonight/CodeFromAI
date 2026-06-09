"""Phase 13: --path-hierarchy off|auto."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_path_hierarchy_off(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "off.hch.db"
    store = build_index_from_filelist(
        str(SYN), str(db), top_module="deep_soc_top", path_hierarchy_mode="off"
    )
    assert store.get_meta("hierarchy_source") == "ast"
    assert store.get_meta("path_hierarchy_used") == "0"
    n = store.count_instances()
    store.close()
    assert n < 100