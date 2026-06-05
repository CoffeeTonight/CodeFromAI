"""Phase 25: ambiguous generate branches, unresolved flat rows, inst_tags round-trip."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.requires_engine
def test_ambiguous_generate_branches():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      generate
        if (ENABLE) begin : g_if
          child u_if();
        end else begin : g_else
          child u_else();
        end
      endgenerate
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_ambig.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    branches = {e.generate_branch for e in mods["top"].instances}
    paths = {e.generate_path for e in mods["top"].instances}
    assert "if_true" in branches or "if_false" in branches
    assert any("if_true" in p or "if_false" in p for p in paths)


@pytest.mark.requires_engine
def test_unresolved_flat_instance_tags(tmp_path):
    from hch.index.loader import build_index_from_modules
    from hch.index.store import HierarchyStore
    from hch.schema import InstanceEdge, ModuleRecord

    top = ModuleRecord(module_name="top", file_path="/tmp/top.v")
    top.instances.append(
        InstanceEdge(
            parent_module="top",
            inst_name="u_miss",
            child_module="missing_mod",
            file_path="/tmp/top.v",
        )
    )
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db = tf.name
    build_index_from_modules({"top": top}, db, top_module="top")
    store = HierarchyStore(db)
    flat = store.load_flat_instances()
    store.close()
    miss = [r for r in flat if "u_miss" in r.full_path or r.module == "missing_mod"]
    assert miss
    row = miss[0]
    assert row.is_unresolved or row.child_kind == "unresolved"


@pytest.mark.requires_engine
def test_flat_inst_tags_roundtrip(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    db = tmp_path / "tags_flat.hch.db"
    build_index_from_filelist(str(GEN / "filelist.f"), str(db), top_module="top_soc")
    store = HierarchyStore(str(db))
    flat = store.load_flat_instances()
    exported = store.export_instance_dicts()
    store.close()
    gen_rows = [r for r in flat if r.in_generate]
    assert gen_rows, "expected in_generate on flat rows from gen_ifdef_generate"
    exp_gen = [e for e in exported if e.get("in_generate")]
    assert exp_gen
    row = gen_rows[0]
    assert row.generate_path or row.in_generate


@pytest.mark.requires_engine
def test_module_inst_json_tags_roundtrip(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    db = tmp_path / "mod_tags.hch.db"
    build_index_from_filelist(str(GEN / "filelist.f"), str(db), top_module="top_soc")
    store = HierarchyStore(str(db))
    mods = store.load_all_modules()
    top = mods.get("top_soc")
    store.close()
    assert top is not None
    assert any(e.in_generate for e in top.instances)
    assert any(e.generate_path for e in top.instances if e.in_generate)