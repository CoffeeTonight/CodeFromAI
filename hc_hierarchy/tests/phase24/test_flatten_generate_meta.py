"""Phase 24: flatten_warnings meta and generate unreachable branch counts."""

import json
from pathlib import Path

import pytest


@pytest.mark.requires_engine
def test_generate_unreachable_count_if_true():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees, get_last_extract_stats

    code = """
    module top;
      generate
        if (1) begin : g_if
          child u_on();
        end else begin : g_else
          child u_off();
        end
      endgenerate
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_gen_unreach.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    names = {e.inst_name for e in mods["top"].instances}
    stats = get_last_extract_stats()
    assert "u_on" in names
    assert "u_off" not in names
    assert stats.get("generate_unreachable_edge_count", 0) >= 1


@pytest.mark.requires_engine
def test_flatten_warnings_on_cycle():
    from hch.index.loader import build_index_from_modules
    from hch.schema import InstanceEdge, ModuleRecord

    a = ModuleRecord(module_name="a", file_path="/tmp/a.v")
    b = ModuleRecord(module_name="b", file_path="/tmp/b.v")
    a.instances.append(
        InstanceEdge(parent_module="a", inst_name="u_b", child_module="b", file_path="/tmp/a.v")
    )
    b.instances.append(
        InstanceEdge(parent_module="b", inst_name="u_a", child_module="a", file_path="/tmp/b.v")
    )
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db = tf.name
    store = build_index_from_modules(
        {"a": a, "b": b},
        db,
        top_module="a",
    )
    warns = json.loads(store.get_meta("flatten_warnings_json", "[]"))
    cycle_flag = store.get_meta("flatten_cycle_warning")
    store.close()
    assert cycle_flag == "1"
    assert warns and any("cycle" in w for w in warns)


@pytest.mark.requires_engine
def test_flatten_warnings_meta_in_filelist_index(tmp_path):
    from hch.index.loader import build_index_from_filelist

    code = """
    module a;
      b u();
    endmodule
    module b;
      a v();
    endmodule
    """
    rtl = tmp_path / "cyc.v"
    rtl.write_text(code, encoding="utf-8")
    fl = tmp_path / "cyc.f"
    fl.write_text(str(rtl), encoding="utf-8")
    db = tmp_path / "cyc.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="a")
    warns = json.loads(store.get_meta("flatten_warnings_json", "[]"))
    store.close()
    assert warns