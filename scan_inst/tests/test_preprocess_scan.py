"""Preprocessor + instance scan tests."""

from __future__ import annotations

from pathlib import Path

from scan_inst.filelist import parse_filelist
from scan_inst.preprocess import apply_ifdef_filter, preprocess_file, strip_comments
from scan_inst.scan import flatten, scan_preprocessed


def test_strip_comments():
    t = "a // c\n/* x */ b"
    assert strip_comments(t) == "a \n b"


def test_ifdef_filter_single_line():
    src = "`ifdef GHOST assign link=src; `else assign link=1'b0; `endif"
    off = apply_ifdef_filter(src, {})
    assert off == "assign link=1'b0;"
    on = apply_ifdef_filter(src, {"GHOST": "1"})
    assert on == "assign link=src;"


def test_ifdef_filter():
    src = """
`ifdef USE_A
  child_a u_a ();
`else
  child_b u_b ();
`endif
"""
    on = apply_ifdef_filter(src, {"USE_A": "1"})
    assert "u_a" in on and "u_b" not in on
    off = apply_ifdef_filter(src, {"USE_A": "0"})
    assert "u_b" in off and "u_a" not in off


def test_include_and_define(tmp_path: Path):
    inc = tmp_path / "cfg.vh"
    inc.write_text(
        "`define USE_PCIE 1\n`ifdef USE_PCIE\n",
        encoding="utf-8",
    )
    rtl = tmp_path / "top.v"
    rtl.write_text(
        "`include \"cfg.vh\"\n"
        "module top;\n"
        "  pcie u_p ();\n"
        "`else\n"
        "  uart u_u ();\n"
        "`endif\n"
        "endmodule\n",
        encoding="utf-8",
    )
    text = preprocess_file(rtl, [tmp_path], {"USE_PCIE": "1"})
    mods = scan_preprocessed(text, str(rtl))
    assert "top" in mods
    assert any(e.child_module == "pcie" for e in mods["top"].instances)
    assert not any(e.child_module == "uart" for e in mods["top"].instances)


def test_bind_skipped(tmp_path: Path):
    rtl = tmp_path / "t.v"
    rtl.write_text(
        "module top;\n"
        "  cpu u_c ();\n"
        "endmodule\n"
        "bind top extra u_e ();\n"
        "module cpu; endmodule\n"
        "module extra; endmodule\n",
        encoding="utf-8",
    )
    text = preprocess_file(rtl, [], {})
    mods = scan_preprocessed(text, str(rtl))
    paths = flatten(mods, "top")
    assert [r.full_path for r in paths] == ["top", "top.u_c"]


def test_filelist_nested_f_lowercase(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "child.v").write_text("module child; endmodule\n", encoding="utf-8")
    (tmp_path / "top.v").write_text(
        "module top;\n  child u_c ();\nendmodule\n",
        encoding="utf-8",
    )
    (sub / "sub.f").write_text("child.v\n", encoding="utf-8")
    top_f = tmp_path / "top.f"
    top_f.write_text(f"-f sub/sub.f\ntop.v\n", encoding="utf-8")
    fl = parse_filelist(str(top_f))
    assert len(fl.source_files) == 2


def test_filelist_nested_F_uppercase(tmp_path: Path):
    """-F: nested from index_cwd, inner paths from index_cwd too."""
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "child.v").write_text("module child; endmodule\n", encoding="utf-8")
    (rtl / "top.v").write_text(
        "module top;\n  child u_c ();\nendmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "nested.f").write_text("rtl/child.v\n", encoding="utf-8")
    top_f = tmp_path / "top.f"
    top_f.write_text("-F nested.f\nrtl/top.v\n", encoding="utf-8")
    fl = parse_filelist(str(top_f), index_cwd=str(tmp_path))
    assert len(fl.source_files) == 2


def test_end_to_end_cli(tmp_path: Path, capsys):
    (tmp_path / "a.v").write_text(
        "module top;\n  sub u_s ();\nendmodule\nmodule sub;\n  leaf u_l ();\nendmodule\nmodule leaf; endmodule\n",
        encoding="utf-8",
    )
    fl = tmp_path / "d.f"
    fl.write_text(f"{tmp_path / 'a.v'}\n", encoding="utf-8")
    out = tmp_path / "out.tsv"
    from scan_inst.cli import main

    assert main([str(fl), "--top", "top", "-o", str(out), "--max-depth", "2"]) == 0
    text = out.read_text(encoding="utf-8")
    assert "top.u_s" in text
    assert "top.u_s.u_l" in text