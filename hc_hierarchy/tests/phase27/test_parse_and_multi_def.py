"""Per-file parse diagnostics and multi-def module_ref rows."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_parse_errors_per_file(tmp_path):
    from hch.ingest.ingest import get_last_parse_meta, ingest_filelist_result

    good = tmp_path / "good.v"
    good.write_text("module good; endmodule\n", encoding="utf-8")
    bad = tmp_path / "bad.v"
    bad.write_text("module bad; assign x = ; endmodule\n", encoding="utf-8")
    top = tmp_path / "top.v"
    top.write_text("module top; good u1(); bad u2(); endmodule\n", encoding="utf-8")
    fl = tmp_path / "t.f"
    fl.write_text(f"{top}\n{good}\n{bad}\n", encoding="utf-8")

    from hch.ingest.filelist import parse_filelist_simple

    fl_res = parse_filelist_simple(str(fl), index_cwd=tmp_path)
    ingest_filelist_result(fl_res, index_cwd=tmp_path)
    meta = get_last_parse_meta()
    by_file = json.loads(meta.get("parse_errors_json", "{}"))
    bad_key = str(bad.resolve())
    assert int(by_file.get(bad_key, {}).get("errors", 0)) >= 1
    good_key = str(good.resolve())
    assert int(by_file.get(good_key, {}).get("errors", 0)) == 0


@pytest.mark.requires_engine
def test_multi_def_module_ref_rows(tmp_path):
    from hch.index.loader import build_index_from_modules
    from hch.index.store import HierarchyStore
    from hch.ingest.merge import merge_module_records
    from hch.schema import ModuleRecord

    a = tmp_path / "dup_a.v"
    b = tmp_path / "dup_b.v"
    a.write_text("module dup; endmodule\n", encoding="utf-8")
    b.write_text("module dup; endmodule\n", encoding="utf-8")
    parent = tmp_path / "parent.v"
    parent.write_text("module parent; dup u(); endmodule\n", encoding="utf-8")

    merged: dict = {}
    merge_module_records(merged, {"dup": ModuleRecord(module_name="dup", file_path=str(a))})
    merge_module_records(merged, {"dup": ModuleRecord(module_name="dup", file_path=str(b))})
    merge_module_records(
        merged,
        {
            "parent": ModuleRecord(
                module_name="parent",
                file_path=str(parent),
                instances=[],
            )
        },
    )
    db = tmp_path / "md.hch.db"
    build_index_from_modules(merged, str(db), top_module="parent")
    store = HierarchyStore(str(db))
    rows = store.conn.execute(
        "SELECT module_ref FROM modules WHERE module_name='dup' ORDER BY module_ref"
    ).fetchall()
    store.close()
    assert len(rows) >= 2
    refs = {r[0] for r in rows}
    assert any("dup_a.v" in r for r in refs)
    assert any("dup_b.v" in r for r in refs)