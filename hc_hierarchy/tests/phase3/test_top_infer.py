"""Auto-detect primary top when --top is omitted."""

from pathlib import Path

import pytest

from hch.paths import design_dir

FILELIST = design_dir("HDLforAST") / "filelist.f"


@pytest.mark.requires_engine
def test_infer_primary_top_module():
    from hch.engine.availability import check_engine
    from hch.ingest.ingest import ingest_filelist
    from hch.ingest.top_infer import infer_primary_top

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    mods = ingest_filelist(FILELIST, index_cwd=str(FILELIST.parent))
    inferred = infer_primary_top(mods)
    assert inferred.primary == "top_module"
    assert "test_module" in inferred.all_tops
    assert inferred.method in ("stem_and_subtree", "single_uninstantiated")


@pytest.mark.requires_engine
def test_index_without_cli_top(tmp_path):
    from hch.apps.api.db_service import HierarchyDbService
    from hch.engine.availability import check_engine
    from hch.index.loader import build_index_from_filelist

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)

    db = tmp_path / "auto.hch.db"
    store = build_index_from_filelist(
        str(FILELIST),
        str(db),
        index_cwd=str(FILELIST.parent),
    )
    assert store.get_meta("top_inference") in (
        "stem_and_subtree",
        "single_uninstantiated",
    )
    assert store.get_meta("top_modules_json") == '["top_module"]'
    all_paths = {
        r[0] for r in store.conn.execute("SELECT full_path FROM instances").fetchall()
    }
    store.close()
    assert "top_module.u_middle_0.u_subTop_0" in all_paths
    assert "test_module.u_middle" in all_paths

    svc = HierarchyDbService(str(db))
    assert [r["full_path"] for r in svc.tree_children(None)] == ["top_module"]
    svc.close()