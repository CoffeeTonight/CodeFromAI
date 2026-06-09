"""Missing filelist RTL: index continues; source API returns missing payload."""

import json
from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

FILELIST = unified_filelist()


@pytest.mark.requires_engine
def test_meta_lists_missing_files(tmp_path):
    from hch.apps.api.db_service import HierarchyDbService
    from hch.engine.availability import check_engine
    from hch.index.loader import build_index_from_filelist

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "miss.hch.db"
    build_index_from_filelist(
        str(FILELIST),
        str(db),
        index_cwd=str(unified_verify_dir()),
    ).close()

    svc = HierarchyDbService(str(db))
    meta = svc.meta()
    missing = meta.get("missing_files") or []
    assert meta.get("missing_file_count", 0) >= 1
    assert any("mid_module.v" in p or "test_top.v" in p for p in missing)
    svc.close()


def test_read_source_missing_on_disk(tmp_path):
    from hch.apps.api.db_service import HierarchyDbService
    from hch.index.store import HierarchyStore

    db = tmp_path / "src.hch.db"
    store = HierarchyStore(str(db))
    ghost = str((tmp_path / "ghost.v").resolve())
    store._upsert_file(ghost)
    store.set_meta("filelist_errors", json.dumps([f"Source not found: {ghost}"]))
    store.set_meta(
        "parse_errors_json",
        json.dumps(
            {
                ghost: {
                    "errors": 1,
                    "warnings": 0,
                    "status": "missing",
                    "messages": ["missing"],
                }
            }
        ),
    )
    store.conn.commit()
    store.close()

    svc = HierarchyDbService(str(db))
    meta = svc.meta()
    assert ghost in meta["missing_files"]
    payload = svc.read_source(ghost)
    assert payload["missing"] is True
    assert "not found" in payload["error"].lower()
    assert payload["content"] == ""
    svc.close()