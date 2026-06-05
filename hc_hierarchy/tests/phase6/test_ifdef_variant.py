"""Item 2: ifdef variant instance-set golden."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / "design" / "extras" / "gen_ifdef_generate"
TOP = GEN_DIR / "rtl" / "top_soc.v"


@pytest.mark.requires_engine
def test_ifdef_variant_differs():
    from hch.ingest.ifdef_variant import compare_instance_sets, instance_set_under_top
    from hch.ingest.ingest import ingest_source_files

    inc = [str(GEN_DIR)]
    with_alt = ingest_source_files(
        [TOP],
        include_dirs=inc,
        defines={"ENABLE_GEN": "1", "USE_ALT": "1"},
    )
    without_alt = ingest_source_files(
        [TOP],
        include_dirs=inc,
        defines={"ENABLE_GEN": "1"},
    )
    left = instance_set_under_top(with_alt, "top_soc")
    right = instance_set_under_top(without_alt, "top_soc")
    diff = compare_instance_sets(left, right)
    assert ("u_alt", "leaf_cell") in diff["only_left"]
    assert ("u_default", "leaf_cell") in diff["only_right"]
    assert any(n == "u_cell" for n, _ in diff["common"])


@pytest.mark.requires_engine
def test_ifdef_meta_on_index(tmp_path):
    from hch.index.loader import build_index_from_filelist

    fl = GEN_DIR / "filelist.f"
    db = tmp_path / "alt.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="top_soc")
    defines = store.get_meta("defines_json", "{}")
    store.close()
    assert "USE_ALT" in defines