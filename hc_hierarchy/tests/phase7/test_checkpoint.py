"""Phase 7: batched ingest + checkpoint resume."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QUICK = ROOT / "design" / "synthetic_deep_rtl" / "quick.hc.f"


@pytest.mark.requires_engine
def test_batched_index_resume(tmp_path):
    from hch.index.batched_loader import build_index_batched
    from hch.index.store import HierarchyStore

    if not QUICK.exists():
        pytest.skip(f"missing {QUICK}")

    db = tmp_path / "resume.hch.db"
    store1 = build_index_batched(
        str(QUICK), str(db), top_module="deep_soc_top", batch_size=8, force=True
    )
    n1 = store1.count_modules()
    done1 = store1.get_meta("checkpoint_files")
    store1.close()
    assert n1 >= 50
    assert done1

    # Simulate resume: force=False should skip already-done sources
    store2 = build_index_batched(
        str(QUICK), str(db), top_module="deep_soc_top", batch_size=8, resume=True
    )
    n2 = store2.count_modules()
    complete = store2.get_meta("indexing_complete")
    store2.close()
    assert n2 == n1
    assert complete == "1"


@pytest.mark.requires_engine
def test_store_roundtrip_instances(tmp_path):
    from hch.ingest.ingest import ingest_source_files
    from hch.index.store import HierarchyStore

    top = ROOT / "design" / "synthetic_deep_rtl" / "rtl" / "deep_soc_top.v"
    if not top.exists():
        pytest.skip("deep_soc_top missing")
    mods = ingest_source_files([top], include_dirs=[str(top.parent)])
    db = tmp_path / "rt.hch.db"
    store = HierarchyStore(str(db))
    store.load_modules(mods.values())
    back = store.load_all_modules()
    store.close()
    assert "deep_soc_top" in back
    assert len(back["deep_soc_top"].instances) >= 5