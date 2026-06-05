"""Phase 11: bind CU, interface array, package."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_top_level_bind():
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(ROOT / "design/extras/parse_bind/filelist.f")
    top = mods["top_bind_cu"]
    assert any(b.inst_name == "u_bind" for b in top.binds)
    assert any(e.inst_name == "u_bind" and e.via_bind for e in top.instances)


@pytest.mark.requires_engine
def test_interface_instance_array():
    from hch.ingest.ingest import ingest_filelist

    fl = ROOT / "design/extras/sv_interface/filelist.f"
    mods = ingest_filelist(fl)
    names = {e.inst_name for e in mods["top_if"].instances}
    assert "u_bus[0]" in names
    assert "u_bus[1]" in names


@pytest.mark.requires_engine
def test_package_indexed():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    p = Path("/tmp/hch_pkg_idx.sv")
    p.write_text("package pkg_a; endpackage\nmodule m; endmodule\n", encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    assert "pkg_a" in mods
    assert mods["pkg_a"].module_kind == "package"