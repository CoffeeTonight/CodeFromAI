"""Tier E: prune compile sources to AST closure from top (fix duplicate modules)."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN_FULL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"
GEN_FL = ROOT / "design/extras/gen_ifdef_generate/filelist.f"


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_ingest_instance_edge_file_paths():
    from hch.ingest.filelist import parse_filelist_simple
    from hch.ingest.ingest import ingest_filelist_result

    fl = parse_filelist_simple(str(SYN_FULL))
    mods = ingest_filelist_result(fl)
    top = mods["deep_soc_top"]
    assert top.file_path.endswith("deep_soc_top.v")
    for edge in top.instances:
        assert edge.file_path.endswith("deep_soc_top.v"), edge.inst_name


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_prune_never_returns_full_filelist_on_seed():
    from hch.engine.elab_source_prune import (
        build_module_path_index,
        prune_sources_for_elab,
    )
    from hch.ingest.elab_fast_ingest import _top_module_seed
    from hch.ingest.filelist import parse_filelist_simple

    fl = parse_filelist_simple(str(SYN_FULL))
    sources = [str(p) for p in fl.source_files]
    idx = build_module_path_index(sources)
    top = idx.get("deep_soc_top", [None])[0]
    assert top
    seed = _top_module_seed(top, "deep_soc_top")
    pruned = prune_sources_for_elab(
        seed, ["deep_soc_top"], all_sources=sources, module_index=idx
    )
    assert len(pruned) == 8
    assert len(pruned) < len(sources) // 2


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_prune_sources_synthetic_deep():
    from hch.engine.elab_source_prune import prune_sources_for_elab
    from hch.ingest.filelist import parse_filelist_simple
    from hch.ingest.ingest import ingest_filelist_result

    fl = parse_filelist_simple(str(SYN_FULL))
    mods = ingest_filelist_result(fl)
    sources = [str(p) for p in fl.source_files]
    pruned = prune_sources_for_elab(
        mods, ["deep_soc_top"], all_sources=sources
    )
    assert len(pruned) == 8
    assert any(p.endswith("deep_soc_top.v") for p in pruned)


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_elab_fast_ingest_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "fast.hch.db"
    store = build_index_from_filelist(
        str(SYN_FULL),
        str(db),
        top_module="deep_soc_top",
        elaborate=True,
        elab_fast=True,
    )
    assert store.get_meta("ingest_mode") == "fast"
    assert store.get_meta("elab_fast_ingest") == "1"
    assert store.get_meta("tier_e_single_pass") == "1"
    assert int(store.get_meta("ingest_source_count", "0")) <= 16
    assert int(store.get_meta("ingest_pruned_from", "0")) > 100
    store.close()


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_elab_synthetic_deep_top_succeeds(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "syn_elab.hch.db"
    store = build_index_from_filelist(
        str(SYN_FULL),
        str(db),
        top_module="deep_soc_top",
        elaborate=True,
    )
    assert store.get_meta("elab_succeeded") == "1"
    assert store.get_meta("elab_partial") == "0"
    assert store.get_meta("hierarchy_source") == "elab"
    n = store.count_instances()
    store.close()
    assert n == 8


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_elab_pruned_mode_when_closure_over_gate(tmp_path):
    """Large closure must still compile pruned sources, not all 991 RTL."""
    from hch.ingest.elab_fast_ingest import tier_e_index_build
    from hch.ingest.filelist_cache import parse_filelist_cached

    fl = parse_filelist_cached(str(SYN_FULL))
    _, res, meta = tier_e_index_build(
        fl,
        ["deep_soc_top"],
        elab_fast=True,
        max_pruned=4,
        max_ratio=0.01,
    )
    assert meta["ingest_mode"] == "pruned"
    assert meta.get("tier_e_single_pass") == "0"
    assert int(meta["ingest_source_count"]) == 8
    assert res.succeeded
    assert len(res.instances) == 8


@pytest.mark.requires_engine
def test_elab_gen_ifdef_still_succeeds(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "gen.hch.db"
    store = build_index_from_filelist(
        str(GEN_FL), str(db), top_module="top_soc", elaborate=True
    )
    assert store.get_meta("elab_succeeded") == "1"
    store.close()