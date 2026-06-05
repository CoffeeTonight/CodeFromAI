"""Path-derived hierarchy for synthetic deep RTL (u_* directory layout)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_path_flatten_full_synthetic_count():
    from hch.ingest.filelist import parse_filelist_simple
    from hch.ingest.hierarchy_build import elaborate_flat, elaborate_flat_with_sources
    from hch.ingest.ingest import ingest_filelist_result

    fl = parse_filelist_simple(ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f")
    mods = ingest_filelist_result(fl)
    sources = [str(p) for p in fl.source_files]

    shallow = elaborate_flat(mods, top_module="deep_soc_top")
    deep, _src, _aug = elaborate_flat_with_sources(
        mods, sources=sources, top_module="deep_soc_top"
    )

    assert len(shallow) <= 16
    assert len(deep) >= 500
    assert max(f.depth for f in deep) >= 5

    ecc = [f for f in deep if f.full_path.startswith("deep_soc_top.u_ecc_engine_00.")]
    assert len(ecc) >= 100


@pytest.mark.requires_engine
def test_path_flatten_does_not_break_hdlforast(tmp_path):
    from hch.paths import design_dir
    from hch.index.loader import build_index_from_filelist

    fl = design_dir("HDLforAST") / "filelist.f"
    if not fl.exists():
        pytest.skip(f"missing {fl}")

    db = tmp_path / "hdl.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="top_module")
    n = store.count_instances()
    store.close()
    assert n >= 3