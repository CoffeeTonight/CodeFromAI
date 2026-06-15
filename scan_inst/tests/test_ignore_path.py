"""ignore-path pattern matching and fast stub scan."""

from __future__ import annotations

from pathlib import Path

from scan_inst.ignore_path import partition_sources, source_path_matches
from scan_inst.index import DesignIndex


def test_source_path_matches_folder_segment():
    path = "/proj/rtl/pcielinktop/foo.v"
    assert source_path_matches(path, ["pcielinktop"])
    assert not source_path_matches(path, ["pcieinnktop"])


def test_ignore_path_skips_preprocess_for_vendor_tree(tmp_path):
    vendor = tmp_path / "pcielinktop"
    vendor.mkdir()
    slow = vendor / "big.v"
    slow.write_text(
        "`include \"missing.vh\"\nmodule big; child u ( ); endmodule\n",
        encoding="utf-8",
    )
    top = tmp_path / "top.v"
    top.write_text(
        "module top; big u_big ( ); endmodule\n",
        encoding="utf-8",
    )

    sources = [str(top), str(slow)]
    index = DesignIndex.build_from_sources(
        sources,
        include_dirs=[],
        defines={},
        jobs=1,
        ignore_paths=["pcielinktop"],
    )
    assert index.get_module("big").stop_reason == "ignorePath"
    assert index.get_module("top") is not None
    assert index.get_module("top").stop_reason == ""


def test_ignore_path_case_insensitive_folder_segment():
    path = "/proj/rtl/PCIeLinkTop/foo.v"
    assert source_path_matches(path, ["pcielinktop"])
    assert source_path_matches(path, ["pciephytop"]) is False


def test_ignore_path_no_read_when_only_referenced(tmp_path):
    vendor = tmp_path / "PCIeLinkTop"
    vendor.mkdir()
    slow = vendor / "big.v"
    slow.write_text(
        "`include \"missing.vh\"\nmodule big; endmodule\n",
        encoding="utf-8",
    )
    top = tmp_path / "top.v"
    top.write_text("module top; big u_big ( ); endmodule\n", encoding="utf-8")

    index = DesignIndex.build_from_sources(
        [str(top), str(slow)],
        include_dirs=[],
        defines={},
        jobs=1,
        ignore_paths=["pcielinktop"],
    )
    assert index.get_module("big").stop_reason == "ignorePath"


def test_partition_sources_splits_ignore(tmp_path):
    a = tmp_path / "pcieinnktop" / "a.v"
    b = tmp_path / "soc" / "b.v"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_text("module a; endmodule\n", encoding="utf-8")
    b.write_text("module b; endmodule\n", encoding="utf-8")
    parse, ignore = partition_sources(
        [str(a), str(b)],
        ["pcielinktop", "pciephyyop"],
    )
    assert str(b) in parse
    assert str(a) in parse  # pcieinnktop not matched by those patterns