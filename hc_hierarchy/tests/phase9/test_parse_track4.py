"""Track 4: hierarchy_source meta; no path fallback on elab failure."""

from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_path_hierarchy_meta_on_synthetic():
    from hch.index.loader import build_index_from_filelist

    fl = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"
    db = Path("/tmp/hch_phase9_path_meta.hch.db")
    if db.exists():
        db.unlink()
    store = build_index_from_filelist(
        str(fl), str(db), top_module="deep_soc_top"
    )
    assert store.get_meta("hierarchy_source") == "path"
    assert store.get_meta("path_hierarchy_used") == "1"
    assert store.get_meta("tier") == "P"
    store.close()


@pytest.mark.requires_engine
def test_elab_fallback_no_path_heuristic(tmp_path):
    import json

    from hch.index.loader import build_index_from_filelist

    top = tmp_path / "bad_top.v"
    top.write_text("module bad_top; foo u (.x(1)); endmodule\n", encoding="utf-8")
    fl = tmp_path / "bad.f"
    fl.write_text(f"{top}\n", encoding="utf-8")
    db = tmp_path / "bad.hch.db"
    store = build_index_from_filelist(
        str(fl), str(db), top_module="bad_top", elaborate=True
    )
    assert store.get_meta("path_hierarchy_used") == "0"
    src = store.get_meta("hierarchy_source", "")
    assert src in ("tier_p_fallback", "elab", "elab_partial")
    if src == "tier_p_fallback":
        assert store.get_meta("elab_fallback") == "tier_p"
    if src == "elab_partial":
        assert store.get_meta("elab_partial") == "1"
    warnings = json.loads(store.get_meta("warnings_json", "[]"))
    succeeded = store.get_meta("elab_succeeded", "1")
    store.close()
    assert warnings or succeeded == "0"


@pytest.mark.requires_engine
def test_hdlforast_uses_ast_not_path(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.paths import unified_filelist, unified_verify_dir

    fl = unified_filelist()
    if not fl.exists():
        pytest.skip(f"missing {fl}")
    db = tmp_path / "hdl.hch.db"
    store = build_index_from_filelist(
        str(fl), str(db), top_module="top_module", index_cwd=str(unified_verify_dir())
    )
    assert store.get_meta("hierarchy_source") == "ast"
    assert store.get_meta("path_hierarchy_used") == "0"
    store.close()