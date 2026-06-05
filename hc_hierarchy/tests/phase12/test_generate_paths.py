"""Phase 12: Tier P generate path segments + macro meta."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.requires_engine
def test_generate_path_segment_in_flatten():
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(GEN / "filelist.f")
    flat = elaborate_flat(mods, top_module="top_soc")
    paths = {f.full_path for f in flat}
    assert any("gen_blk" in p and "u_cell" in p for p in paths)


@pytest.mark.requires_engine
def test_macro_instance_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "gen.hch.db"
    store = build_index_from_filelist(
        str(GEN / "filelist.f"), str(db), top_module="top_soc"
    )
    assert store.get_meta("macro_instance_count") is not None
    store.close()