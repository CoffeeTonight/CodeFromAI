"""Performance helpers: filelist parse cache."""

import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN_FULL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"


@pytest.mark.requires_synthetic_full
def test_filelist_cache_second_parse_is_faster():
    from hch.ingest.filelist_cache import clear_filelist_cache, parse_filelist_cached

    clear_filelist_cache()
    t0 = time.perf_counter()
    parse_filelist_cached(str(SYN_FULL))
    cold = time.perf_counter() - t0
    t1 = time.perf_counter()
    parse_filelist_cached(str(SYN_FULL))
    warm = time.perf_counter() - t1
    assert warm < cold * 0.05 or warm < 0.02


def test_filelist_cache_invalidates_on_nested_f_touch(tmp_path):
    from hch.ingest.filelist_cache import clear_filelist_cache, parse_filelist_cached

    nested = tmp_path / "nested.f"
    top = tmp_path / "top.f"
    rtl = tmp_path / "a.v"
    rtl.write_text("module a; endmodule\n", encoding="utf-8")
    nested.write_text(f"{rtl}\n", encoding="utf-8")
    top.write_text(f"-f {nested.name}\n", encoding="utf-8")

    clear_filelist_cache()
    a = parse_filelist_cached(str(top))
    assert len(a.source_files) == 1

    nested.write_text("// touch\n" + nested.read_text(encoding="utf-8"), encoding="utf-8")
    b = parse_filelist_cached(str(top))
    assert b is not a