"""Phase 10: -y/-v passed to slang preprocessing / compile."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TRACK2 = ROOT / "design" / "extras" / "parse_track2"


def test_filelist_lines_include_y_v():
    from hch.ingest.filelist import parse_filelist_simple
    from hch.ingest.filelist_config import config_from_filelist
    from hch.engine.pyslang_parse import filelist_lines

    fl = parse_filelist_simple(TRACK2 / "filelist.f")
    cfg = config_from_filelist(fl)
    lines = filelist_lines(cfg)
    assert any(l.startswith("-y ") for l in lines)
    assert any("top_bind.v" in l for l in lines)


@pytest.mark.requires_engine
def test_y_dir_resolves_module_not_blackbox():
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(TRACK2 / "filelist.f")
    assert "ram_stub" in mods
    assert mods["ram_stub"].is_blackbox is False
    assert "ram_stub" not in __import__(
        "hch.ingest.unresolved", fromlist=["collect_unresolved_modules"]
    ).collect_unresolved_modules(mods)


@pytest.mark.requires_engine
def test_preprocess_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "lib.hch.db"
    store = build_index_from_filelist(
        str(TRACK2 / "filelist.f"), str(db), top_module="top_bind"
    )
    assert store.get_meta("preprocess_libs_in_driver") == "1"
    assert int(store.get_meta("library_y_count", "0")) >= 1
    store.close()