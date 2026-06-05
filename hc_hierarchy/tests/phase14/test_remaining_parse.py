"""Phase 14: ifdef batch, elab cap/partial, multi-top, module_ref DQL, store tags."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"
IFACE = ROOT / "design" / "extras" / "sv_interface"


@pytest.mark.requires_engine
def test_ifdef_compare_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "ifdef.hch.db"
    store = build_index_from_filelist(
        str(GEN / "filelist.f"),
        str(db),
        top_module="top_soc",
        ifdef_compare=True,
        ifdef_alt="USE_ALT=1",
    )
    raw = store.get_meta("ifdef_variant_diff_json", "{}")
    store.close()
    import json

    diff = json.loads(raw)
    assert diff.get("top_module") == "top_soc"
    only_alt = diff.get("only_alt", [])
    assert only_alt
    flat = " ".join(str(x) for x in only_alt)
    assert "u_alt" in flat


@pytest.mark.requires_engine
def test_generate_else_not_extracted():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top(input clk, rst_n);
      genvar gi;
      generate
        if (1) begin : g_if
          uart16550 u_uart (.clk(clk), .rst_n(rst_n));
        end else begin : g_else
          spi_master u_spi (.clk(clk), .rst_n(rst_n));
        end
      endgenerate
    endmodule
    """
    p = Path("/tmp/hch_gen_else_skip.v")
    p.write_text(code)
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    names = {e.inst_name for e in mods["top"].instances}
    assert "u_uart" in names
    assert "u_spi" not in names


@pytest.mark.requires_engine
def test_elab_instance_cap(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "cap.hch.db"
    store = build_index_from_filelist(
        str(GEN / "filelist.f"),
        str(db),
        top_module="top_soc",
        elaborate=True,
        elab_instance_cap=3,
    )
    n = store.count_instances()
    cap_hit = store.get_meta("elab_instance_cap_hit", "0")
    store.close()
    assert n <= 3
    assert cap_hit == "1"


@pytest.mark.requires_engine
def test_module_ref_dql(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore
    from hch.query.dql.sql_compiler import plan_dql

    top = tmp_path / "dup_a.v"
    top.write_text("module child; endmodule\n", encoding="utf-8")
    top2 = tmp_path / "dup_b.v"
    top2.write_text("module child; endmodule\n", encoding="utf-8")
    parent = tmp_path / "parent.v"
    parent.write_text(
        "module parent; child u(); endmodule\n",
        encoding="utf-8",
    )
    fl = tmp_path / "dup.f"
    fl.write_text(f"{parent}\n{top}\n{top2}\n", encoding="utf-8")
    db = tmp_path / "dup.hch.db"
    build_index_from_filelist(str(fl), str(db), top_module="parent")
    store = HierarchyStore(str(db))
    from hch.schema import ModuleRecord

    store.load_modules(
        [
            ModuleRecord(module_name="child", file_path=str(top2)),
        ]
    )
    ref_rows = store.conn.execute(
        "SELECT module_ref FROM modules WHERE module_name='child'"
    ).fetchall()
    assert len(ref_rows) >= 2
    ref = ref_rows[0][0]
    plan = plan_dql(f'module_ref ~ "*dup_a.v*"')
    store.conn.row_factory = __import__("sqlite3").Row
    hits = store.conn.execute(plan.sql, plan.params).fetchall()
    store.close()
    assert len(hits) >= 1


@pytest.mark.requires_engine
def test_inst_tags_roundtrip(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    db = tmp_path / "tags.hch.db"
    build_index_from_filelist(str(GEN / "filelist.f"), str(db), top_module="top_soc")
    store = HierarchyStore(str(db))
    mods = store.load_all_modules()
    top = mods.get("top_soc")
    store.close()
    assert top is not None
    assert any(e.in_generate for e in top.instances)


@pytest.mark.requires_engine
def test_multi_top_flatten(tmp_path):
    from hch.index.loader import build_index_from_filelist

    a = tmp_path / "a.v"
    b = tmp_path / "b.v"
    a.write_text("module top_a; endmodule\n", encoding="utf-8")
    b.write_text("module top_b; endmodule\n", encoding="utf-8")
    fl = tmp_path / "two.f"
    fl.write_text(f"{a}\n{b}\n", encoding="utf-8")
    db = tmp_path / "two.hch.db"
    store = build_index_from_filelist(
        str(fl), str(db), top_modules=["top_a", "top_b"]
    )
    paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert "top_a" in paths
    assert "top_b" in paths


@pytest.mark.requires_engine
def test_tier_e_interface_elab_paths(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "if.hch.db"
    store = build_index_from_filelist(
        str(IFACE / "filelist.f"),
        str(db),
        top_module="top_if",
        elaborate=True,
    )
    paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert any("top_if" in p for p in paths)
    assert len(paths) >= 2