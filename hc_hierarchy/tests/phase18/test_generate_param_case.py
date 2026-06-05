"""Phase 18: parametric generate loop + case generate."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN_PARAM = ROOT / "design" / "extras" / "parse_gen_param"


@pytest.mark.requires_engine
def test_parametric_depth_unroll():
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.ingest import ingest_filelist

    mods = ingest_filelist(GEN_PARAM / "filelist.f")
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.g[0].u" in paths
    assert "top.g[1].u" in paths


@pytest.mark.requires_engine
def test_case_generate_select_arm():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      generate
        case (1)
          0: child u0();
          1: child u1();
        endcase
      endgenerate
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_casegen.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.case_1.u1" in paths
    assert "top.case_0.u0" not in paths