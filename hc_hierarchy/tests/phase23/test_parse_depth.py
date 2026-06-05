"""Phase 23: parametric instance arrays, while unroll, ifdef multi-DB."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.requires_engine
def test_parametric_instance_array():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      parameter N = 4;
      leaf u[N-1:0]();
    endmodule
    module leaf; endmodule
    """
    p = Path("/tmp/hch_parr.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    names = {e.inst_name for e in mods["top"].instances}
    assert names == {"u[0]", "u[1]", "u[2]", "u[3]"}
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.u[3]" in paths


@pytest.mark.requires_engine
def test_while_generate_unroll_lt():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    code = """
    module top;
      genvar i;
      generate
        while (i < 3) begin : wg
          child u();
        end
      endgenerate
    endmodule
    module child; endmodule
    """
    p = Path("/tmp/hch_while3.v")
    p.write_text(code, encoding="utf-8")
    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    gpaths = {e.generate_path for e in mods["top"].instances}
    assert gpaths == {"wg[0]", "wg[1]", "wg[2]"}
    flat = elaborate_flat(mods, top_module="top")
    paths = {f.full_path for f in flat}
    assert "top.wg[2].u" in paths
    assert "top.wg[3].u" not in paths


@pytest.mark.requires_engine
def test_variant_split_databases(tmp_path):
    from hch.index.loader import build_index_from_filelist

    vdir = tmp_path / "variants"
    db = tmp_path / "combined.hch.db"
    store = build_index_from_filelist(
        str(GEN / "filelist.f"),
        str(db),
        top_module="top_soc",
        variants=[
            ("base", {"USE_ALT": ""}),
            ("alt", {"USE_ALT": "1"}),
        ],
        variant_dir=str(vdir),
    )
    manifest = json.loads(store.get_meta("variant_db_manifest_json", "{}"))
    store.close()
    assert (vdir / "base.hch.db").is_file()
    assert (vdir / "alt.hch.db").is_file()
    assert manifest.get("base") and manifest.get("alt")
    assert (vdir / "variant_db_manifest.json").is_file()