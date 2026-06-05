"""Tier P generate for-loop unroll (literal bounds)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.requires_engine
def test_loop_indices_parser():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.generate_unroll import loop_indices_for_generate

    code = """
    module t;
      genvar i;
      generate
        for (i = 1; i <= 3; i++) begin : g
        end
      endgenerate
    endmodule
    """
    p = Path("/tmp/hch_gen_le.v")
    p.write_text(code, encoding="utf-8")
    tree = parse_syntax_trees([p])[0]
    top = tree.root.members[0]

    def find_loop(node):
        if "LoopGenerate" in str(getattr(node, "kind", "")):
            return node
        for m in getattr(node, "members", []) or []:
            r = find_loop(m)
            if r:
                return r
        b = getattr(node, "block", None)
        return find_loop(b) if b is not None else None

    loop = find_loop(top)
    indices, resolved = loop_indices_for_generate(loop)
    assert indices == [1, 2, 3]
    assert resolved


@pytest.mark.requires_engine
def test_tier_p_generate_loop_paths_match_elab():
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(GEN / "filelist.f")
    flat = elaborate_flat(mods, top_module="top_soc")
    paths = {f.full_path for f in flat}
    assert "top_soc.gen_blk.gen_loop[0].u_cell" in paths
    assert "top_soc.gen_blk.gen_loop[1].u_cell" in paths


@pytest.mark.requires_engine
def test_index_meta_generate_unrolled(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "gen_p.hch.db"
    store = build_index_from_filelist(
        str(GEN / "filelist.f"), str(db), top_module="top_soc"
    )
    assert store.get_meta("tier_p_generate_unrolled") == "1"
    assert int(store.get_meta("generate_loop_unroll_count", "0")) >= 2
    n = store.conn.execute(
        "SELECT COUNT(*) FROM instances WHERE full_path LIKE '%gen_loop[%'"
    ).fetchone()[0]
    store.close()
    assert n >= 2


@pytest.mark.requires_engine
def test_nested_generate_loop():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      genvar i, j;
      generate
        for (i = 0; i < 2; i++) begin : outer
          for (j = 0; j < 2; j++) begin : inner
            leaf u (.x(1));
          end
        end
      endgenerate
    endmodule
    module leaf(input x); endmodule
    """
    p = Path("/tmp/hch_gen_nested.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.outer[0].inner[0].u" in paths
    assert "top.outer[1].inner[1].u" in paths