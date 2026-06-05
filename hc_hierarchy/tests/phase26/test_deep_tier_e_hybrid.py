"""Deep synthetic: path hierarchy + shallow Tier E hybrid."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN_FULL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"


@pytest.mark.requires_engine
@pytest.mark.slow
def test_deep_elab_hybrid_index(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "hybrid.hch.db"
    store = build_index_from_filelist(
        str(SYN_FULL),
        str(db),
        top_module="deep_soc_top",
        elaborate=True,
        elab_deep="hybrid",
    )
    assert store.get_meta("hierarchy_source") == "path_elab_hybrid"
    assert store.get_meta("elab_closure_hybrid") == "1"
    assert store.get_meta("elab_succeeded") == "1"
    assert store.get_meta("path_hierarchy_used") == "1"
    n = store.count_instances()
    store.close()
    assert n >= 900
    assert n <= 1100


@pytest.mark.requires_engine
def test_shallow_elab_still_eight_instances(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "shallow.hch.db"
    store = build_index_from_filelist(
        str(SYN_FULL),
        str(db),
        top_module="deep_soc_top",
        elaborate=True,
        elab_deep="shallow",
    )
    assert store.get_meta("hierarchy_source") == "elab"
    assert store.count_instances() == 8
    store.close()