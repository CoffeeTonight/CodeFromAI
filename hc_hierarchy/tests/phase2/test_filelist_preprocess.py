"""-F preprocessing → pyslang-safe absolute filelist lines."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "multihost_peri_soc"
SYNTH = ROOT / "design" / "synthetic_deep_rtl"


def test_slang_lines_have_no_nested_f_F(tmp_path):
    from hch.ingest.filelist_preprocess import (
        build_slang_filelist_lines,
        expand_filelist,
    )

    top = tmp_path / "top.f"
    sub = tmp_path / "sub.f"
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "leaf.v").write_text("module leaf(); endmodule\n", encoding="utf-8")
    sub.write_text("+define+SUB=1\nrtl/leaf.v\n", encoding="utf-8")
    top.write_text(f"-F {sub.name}\n", encoding="utf-8")

    fl = expand_filelist(top, index_cwd=tmp_path)
    assert not fl.errors
    lines = build_slang_filelist_lines(fl)
    joined = "\n".join(lines)
    assert "-f " not in joined and "-F " not in joined
    assert str((rtl / "leaf.v").resolve()) in joined
    assert "+define+SUB=1" in joined


def test_minus_F_strict_index_cwd_orion(monkeypatch):
    from hch.ingest.filelist import parse_filelist_simple

    if not (DESIGN / "orion_soc.f").exists():
        pytest.skip("multihost_peri_soc not generated")

    import os

    os.environ["ORION_RTL_ROOT"] = str(DESIGN.resolve())
    fl = parse_filelist_simple(
        str(DESIGN / "orion_soc.f"),
        env={"ORION_RTL_ROOT": os.environ["ORION_RTL_ROOT"]},
        index_cwd=DESIGN,
    )
    names = {p.name for p in fl.source_files}
    assert "axi_host_pcie.v" in names
    assert not fl.errors


def test_preprocess_writes_absolute_file(tmp_path):
    from hch.ingest.filelist_preprocess import preprocess_filelist_for_slang

    rtl = tmp_path / "m.v"
    rtl.write_text("module m(); endmodule\n", encoding="utf-8")
    top = tmp_path / "top.f"
    top.write_text(f"{rtl.name}\n", encoding="utf-8")

    prep = preprocess_filelist_for_slang(top, index_cwd=tmp_path, write_path=tmp_path / "out.f")
    text = prep.slang_path.read_text(encoding="utf-8")
    assert "-F" not in text and "-f" not in text
    assert str(rtl.resolve()) in text