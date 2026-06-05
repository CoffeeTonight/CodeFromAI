"""Track 2: -y/-v library stubs and bind directives."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TRACK2 = ROOT / "design" / "extras" / "parse_track2"


def test_filelist_parses_library_dirs():
    from hch.ingest.filelist import parse_filelist_simple

    fl = parse_filelist_simple(TRACK2 / "filelist.f")
    assert fl.library_dirs
    assert any("lib" in str(p) for p in fl.library_dirs)


@pytest.mark.requires_engine
def test_library_blackbox_and_bind(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(TRACK2 / "filelist.f")
    assert "ram_stub" in mods
    # -y lib is preprocessed/parsed: full module, not regex stub
    assert mods["ram_stub"].is_blackbox is False

    top = mods["top_bind"]
    bind_names = {b.inst_name for b in top.binds}
    assert "u_ram" in bind_names
    inst_names = {e.inst_name for e in top.instances}
    assert "u_ram" in inst_names
    assert any(e.via_bind for e in top.instances if e.inst_name == "u_ram")

    db = tmp_path / "t2.hch.db"
    store = build_index_from_filelist(
        str(TRACK2 / "filelist.f"), str(db), top_module="top_bind"
    )
    assert store.get_meta("preprocess_libs_in_driver") == "1"
    assert int(store.get_meta("bind_directive_count", "0")) >= 1
    store.close()