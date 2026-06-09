"""index_cwd, cache key, and slang filelist reuse."""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNTH = ROOT / "design" / "synthetic_deep_rtl"


def test_resolve_index_cwd_env(monkeypatch, tmp_path):
    from hch.ingest.filelist import resolve_index_cwd

    top = tmp_path / "top.f"
    top.write_text("// empty\n", encoding="utf-8")
    monkeypatch.setenv("HCH_INDEX_CWD", str(tmp_path / "run"))
    assert resolve_index_cwd(top) == (tmp_path / "run").resolve()


def test_filelist_cache_differs_by_index_cwd(tmp_path):
    from hch.ingest.filelist_cache import clear_filelist_cache, parse_filelist_cached

    clear_filelist_cache()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    top = tmp_path / "top.f"
    sub = a / "sub.f"
    (a / "rtl").mkdir()
    (a / "rtl" / "m.v").write_text("module m(); endmodule\n", encoding="utf-8")
    sub.write_text("rtl/m.v\n", encoding="utf-8")
    top.write_text(f"-F {sub.name}\n", encoding="utf-8")

    fl_a = parse_filelist_cached(str(top), index_cwd=str(a))
    fl_b = parse_filelist_cached(str(top), index_cwd=str(b))
    assert not fl_a.errors
    assert fl_b.errors


def test_slang_filelist_cache_reuse(tmp_path):
    from hch.ingest.filelist_preprocess import (
        expand_filelist,
        slang_filelist_is_stale,
        write_slang_filelist_cached,
    )

    rtl = tmp_path / "m.v"
    rtl.write_text("module m(); endmodule\n", encoding="utf-8")
    top = tmp_path / "top.f"
    top.write_text(f"{rtl.name}\n", encoding="utf-8")
    fl = expand_filelist(top, index_cwd=tmp_path)
    cache = tmp_path / "out.hch.db"
    p1 = write_slang_filelist_cached(fl, index_cwd=tmp_path, cache_path=cache)
    mt1 = p1.stat().st_mtime
    assert not slang_filelist_is_stale(p1, {str(top): top.stat().st_mtime})
    p2 = write_slang_filelist_cached(fl, index_cwd=tmp_path, cache_path=cache)
    assert p1 == p2
    assert p2.stat().st_mtime == mt1


@pytest.mark.skipif(not (SYNTH / "top_deep_soc.hc.f").exists(), reason="no synthetic RTL")
@pytest.mark.requires_synthetic_full
def test_synthetic_filelist_from_repo_root():
    from hch.ingest.filelist import parse_filelist_simple

    fl = parse_filelist_simple(
        str(SYNTH / "top_deep_soc.hc.f"),
        index_cwd=SYNTH,
    )
    assert not fl.errors
    assert len(fl.source_files) >= 900