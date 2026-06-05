"""Track 1: generate / ifdef / macro tagging (Tier P)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "design" / "extras" / "gen_ifdef_generate"
TOP = GEN_DIR / "rtl" / "top_soc.v"


@pytest.mark.requires_engine
def test_generate_instances_tagged():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    trees = parse_syntax_trees([TOP], include_dirs=[str(GEN_DIR)])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(TOP))}
    gen_edges = [e for e in mods["top_soc"].instances if e.in_generate]
    assert len(gen_edges) >= 1
    assert any(e.inst_name.startswith("u_cell") for e in gen_edges)


@pytest.mark.requires_engine
def test_ifdef_variant_and_meta(tmp_path):
    import json

    from hch.index.loader import build_index_from_filelist
    from hch.ingest.ifdef_variant import compare_instance_sets, instance_set_under_top
    from hch.ingest.ingest import ingest_source_files

    inc = [str(GEN_DIR)]
    with_alt = ingest_source_files(
        [TOP], include_dirs=inc, defines={"USE_ALT": "1"}
    )
    without_alt = ingest_source_files([TOP], include_dirs=inc, defines={})
    diff = compare_instance_sets(
        instance_set_under_top(with_alt, "top_soc"),
        instance_set_under_top(without_alt, "top_soc"),
    )
    assert ("u_alt", "leaf_cell") in diff["only_left"]
    assert ("u_default", "leaf_cell") in diff["only_right"]

    db = tmp_path / "t1.hch.db"
    store = build_index_from_filelist(
        str(GEN_DIR / "filelist.f"), str(db), top_module="top_soc"
    )
    assert store.get_meta("tier_p_generate_unrolled") == "0"
    assert int(store.get_meta("generate_instance_count", "0")) >= 1
    defines = json.loads(store.get_meta("defines_json", "{}"))
    store.close()
    assert "USE_ALT" in defines