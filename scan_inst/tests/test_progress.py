"""Progress reporting during filelist expansion."""

from __future__ import annotations

from scan_inst.filelist import parse_filelist


def test_filelist_progress_messages(tmp_path):
    nested = tmp_path / "nested.f"
    nested.write_text("child.v\n", encoding="utf-8")
    child = tmp_path / "child.v"
    child.write_text("module child; endmodule\n", encoding="utf-8")
    top = tmp_path / "top.f"
    top.write_text(f"-f {nested.name}\n", encoding="utf-8")

    lines: list[str] = []
    fl = parse_filelist(top, on_progress=lines.append)

    assert len(fl.source_files) == 1
    assert any("expanding" in line for line in lines)
    assert any("reading top.f" in line for line in lines)
    assert any("reading nested.f" in line for line in lines)
    assert any("done —" in line for line in lines)