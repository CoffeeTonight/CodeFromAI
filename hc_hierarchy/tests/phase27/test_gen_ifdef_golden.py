"""Golden: generate if (ENABLE) with +define+ — taken branch only."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN_IF = ROOT / "design" / "extras" / "gen_ifdef_in_generate"
GEN_SOC = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.skipif(not (GEN_IF / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_generate_if_enable_define_taken_branch():
    from hch.ingest.ingest import ingest_filelist
    from hch.ingest.ingest import get_last_extract_stats

    mods = ingest_filelist(GEN_IF / "filelist.f", index_cwd=GEN_IF)
    top = mods["top_gen_if"]
    children = {(e.inst_name, e.child_module) for e in top.instances}
    assert ("u_on", "leaf") in children
    assert ("u_off", "leaf") not in children
    stats = get_last_extract_stats()
    assert int(stats.get("generate_branch_ambiguous", 0)) == 0


@pytest.mark.skipif(not (GEN_IF / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_generate_if_enable_zero_else_branch(tmp_path):
    from hch.ingest.filelist import parse_filelist_simple
    from hch.ingest.ingest import ingest_filelist_result

    fl = parse_filelist_simple(str(GEN_IF / "filelist.f"), index_cwd=GEN_IF)
    fl.defines["ENABLE"] = "0"
    mods = ingest_filelist_result(fl, index_cwd=GEN_IF)
    top = mods["top_gen_if"]
    children = {(e.inst_name, e.child_module) for e in top.instances}
    assert ("u_off", "leaf") in children
    assert ("u_on", "leaf") not in children


@pytest.mark.skipif(not (GEN_SOC / "filelist.f").exists(), reason="fixture missing")
@pytest.mark.requires_engine
def test_ifdef_preprocessor_instances_indexed(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    db = tmp_path / "ifdef_soc.hch.db"
    store = build_index_from_filelist(
        str(GEN_SOC / "filelist.f"),
        str(db),
        top_module="top_soc",
        index_cwd=GEN_SOC,
    )
    flat = store.load_flat_instances()
    paths = {r.full_path for r in flat}
    store.close()
    assert any("gen_blk" in p and "u_cell" in p for p in paths)
    assert any("u_default" in p or "u_alt" in p for p in paths)


@pytest.mark.requires_engine
def test_if_generate_truth_ifdef_name():
    from hch.ingest.generate_unroll import if_generate_truth

    class _Node:
        kind = "IfGenerate"

        def __init__(self, text: str):
            self.condition = _Cond(text)

    class _Cond:
        def __init__(self, text: str):
            self.text = text

    node = _Node("`ifdef USE_ALT")
    assert if_generate_truth(node, {"USE_ALT": "1"}) is True
    assert if_generate_truth(node, {"USE_ALT": "0"}) is False
    assert if_generate_truth(node, {}) is None