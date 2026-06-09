"""Web tree roots follow index top_modules_json."""

import pytest

from hch.paths import design_dir

FILELIST = design_dir("HDLforAST") / "filelist.f"


@pytest.mark.requires_engine
def test_tree_children_respect_top_modules(tmp_path):
    from hch.apps.api.db_service import HierarchyDbService
    from hch.engine.availability import check_engine
    from hch.index.loader import build_index_from_filelist

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "toponly.hch.db"
    build_index_from_filelist(
        str(FILELIST),
        str(db),
        top_module="top_module",
        index_cwd=str(FILELIST.parent),
    ).close()

    svc = HierarchyDbService(str(db))
    roots = svc.tree_children(None)
    assert [r["full_path"] for r in roots] == ["top_module"]
    kids = svc.tree_children("top_module")
    assert {r["full_path"] for r in kids} == {
        "top_module.u_middle_0",
        "top_module.u_middle_a",
    }
    grand = svc.tree_children("top_module.u_middle_0")
    assert {r["full_path"] for r in grand} == {
        "top_module.u_middle_0.u_subTop_0",
        "top_module.u_middle_0.u_sub_1",
    }
    svc.close()