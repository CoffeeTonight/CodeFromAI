"""Tier contract v1: compile context + hierarchy mode decision."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_compile_context_pruned_clears_filelist_path():
    from hch.ingest.compile_context import PyslangCompileContext
    from hch.ingest.filelist import parse_filelist_simple

    fl = parse_filelist_simple(
        str(ROOT / "design/extras/multi_def_dup/filelist.f"),
        index_cwd=ROOT / "design/extras/multi_def_dup",
    )
    ctx = PyslangCompileContext.for_pruned_closure(
        fl, [str(ROOT / "design/extras/multi_def_dup/rtl/top_dup.v")]
    )
    assert ctx.mode == "pruned"
    assert ctx.filelist_path is None
    assert len(ctx.source_files) == 1


def test_choose_hierarchy_mode_auto_large():
    from hch.index.hierarchy_mode import choose_hierarchy_mode
    from hch.ingest.filelist import parse_filelist_simple

    fl = parse_filelist_simple(str(ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"))
    decision = choose_hierarchy_mode(
        elab_deep="auto",
        primary_top="deep_soc_top",
        pruned=["a.v"] * 8,
        mod_index={"dup": ["x.v", "y.v"]},
        fl=fl,
        use_hybrid_heuristic=True,
    )
    assert decision.use_path_elab_hybrid
    assert decision.mode == "hybrid"