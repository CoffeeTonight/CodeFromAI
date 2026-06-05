"""Phase 22: while generate placeholder, macro tagging, loop step, Tier E bind merge."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_while_generate_placeholder():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      parameter RUN = 1;
      generate
        while (RUN) begin : wg
          child u();
        end
      endgenerate
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_whilegen.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.wg[0].u" in paths

    p.write_text(code.replace("RUN = 1", "RUN = 0"), encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    flat = elaborate_flat(mods, top_module="top")
    assert not any("u" in f.full_path for f in flat if f.full_path != "top")


@pytest.mark.requires_engine
def test_generate_loop_step_two():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      genvar i;
      generate
        for (i = 0; i < 4; i = i + 2) begin : g
          child u();
        end
      endgenerate
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_step2.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.g[0].u" in paths
    assert "top.g[2].u" in paths
    assert "top.g[1].u" not in paths


@pytest.mark.requires_engine
def test_macro_instance_tagging():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    `define INST(n) child u_``n ();
    module top;
      `INST(a)
      `INST(b)
      child u_plain();
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_macro.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    top = mods["top"]
    macro_insts = [e for e in top.instances if e.from_macro]
    names = {e.inst_name for e in macro_insts}
    assert "u_a" in names
    assert "u_b" in names
    assert "u_plain" not in names


@pytest.mark.requires_engine
def test_tier_e_bind_merge_meta():
    from hch.index.loader import build_index_from_filelist

    rtl = ROOT / "design" / "extras" / "parse_bind" / "rtl"
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".f", delete=False) as tf:
        tf.write(f"{rtl}/top_bind_cu.v\n{rtl}/bind_hier.v\n")
        flist = tf.name
    db = Path(flist).with_suffix(".hch.db")
    store = build_index_from_filelist(
        flist, str(db), top_module="top", elaborate=True
    )
    paths = {
        r[0]
        for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    merge_added = store.get_meta("tier_e_bind_merge_added")
    store.close()
    assert any("u_sub" in p and "u_bind" in p for p in paths)
    assert merge_added is not None