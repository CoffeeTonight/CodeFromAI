"""Phase 26: filelist -top, package symbols, DQL child_kind, multi-def, library map."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_filelist_top_directive(tmp_path):
    from hch.index.loader import build_index_from_filelist

    rtl = tmp_path / "top.v"
    rtl.write_text("module my_top; endmodule\n", encoding="utf-8")
    fl = tmp_path / "design.f"
    fl.write_text(f"-top my_top\n{rtl}\n", encoding="utf-8")
    db = tmp_path / "t.hch.db"
    store = build_index_from_filelist(str(fl), str(db))
    tops = json.loads(store.get_meta("filelist_top_modules_json", "[]"))
    paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert tops == ["my_top"]
    assert "my_top" in paths


@pytest.mark.requires_engine
def test_package_symbols_indexed():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    package pkg_a;
      parameter W = 8;
      typedef logic [7:0] byte_t;
    endpackage
    module m; endmodule
    """
    p = Path("/tmp/hch_pkg_sym.v")
    p.write_text(code, encoding="utf-8")
    mods = {m.module_name: m for m in extract_modules_from_trees(parse_syntax_trees([p]), str(p))}
    pkg = mods["pkg_a"]
    assert pkg.module_kind == "package"
    assert pkg.parameters.get("param_W") == "8"
    assert "typedef_byte_t" in pkg.parameters


@pytest.mark.requires_engine
def test_dql_child_kind_unresolved(tmp_path):
    from hch.index.loader import build_index_from_modules
    from hch.index.store import HierarchyStore
    from hch.query.dql.sql_compiler import plan_dql
    from hch.schema import InstanceEdge, ModuleRecord

    top = ModuleRecord(module_name="top", file_path="/tmp/t.v")
    top.instances.append(
        InstanceEdge(
            parent_module="top",
            inst_name="u_x",
            child_module="missing_cell",
            file_path="/tmp/t.v",
        )
    )
    db = tmp_path / "ck.hch.db"
    build_index_from_modules({"top": top}, str(db), top_module="top")
    store = HierarchyStore(str(db))
    plan = plan_dql('child_kind = "unresolved"')
    hits = store.conn.execute(plan.sql, plan.params).fetchall()
    store.close()
    assert hits


@pytest.mark.requires_engine
def test_multi_def_modules_json(tmp_path):
    from hch.ingest.merge import merge_module_records
    from hch.index.loader import build_index_from_modules
    from hch.index.store import HierarchyStore
    from hch.schema import ModuleRecord

    a = ModuleRecord(module_name="dup", file_path=str(tmp_path / "a.v"))
    b = ModuleRecord(module_name="dup", file_path=str(tmp_path / "b.v"))
    merged: dict = {}
    merge_module_records(merged, {"dup": a})
    merge_module_records(merged, {"dup": b})
    assert "_definition_paths" in merged["dup"].parameters
    db = tmp_path / "md.hch.db"
    build_index_from_modules(merged, str(db), top_module="dup")
    store = HierarchyStore(str(db))
    md = json.loads(store.get_meta("multi_def_modules_json", "{}"))
    store.close()
    assert "dup" in md
    assert len(md["dup"]) >= 2


@pytest.mark.requires_engine
def test_merge_prefers_rtl_over_blackbox():
    from hch.ingest.merge import merge_module_records
    from hch.schema import ModuleRecord

    bb = ModuleRecord(module_name="cell", file_path="/lib/cell.v", is_blackbox=True)
    bb.ports = []
    rtl = ModuleRecord(module_name="cell", file_path="/rtl/cell.v")
    rtl.ports.append(__import__("hch.schema", fromlist=["PortRecord"]).PortRecord(name="clk"))
    merged = {"cell": bb}
    merge_module_records(merged, {"cell": rtl})
    assert not merged["cell"].is_blackbox
    assert merged["cell"].file_path.endswith("rtl/cell.v")


@pytest.mark.requires_engine
def test_library_cell_map_meta():
    from hch.ingest.filelist import parse_filelist_simple
    from hch.ingest.ingest import ingest_filelist_result

    track2 = ROOT / "design" / "extras" / "parse_track2"
    fl = track2 / "filelist.f"
    if not fl.exists():
        pytest.skip("parse_track2 missing")
    result = parse_filelist_simple(str(fl))
    ingest_filelist_result(result)
    from hch.ingest.ingest import get_last_parse_meta

    meta = get_last_parse_meta()
    cell_map = json.loads(meta.get("library_cell_map_json", "{}"))
    assert isinstance(cell_map, dict)