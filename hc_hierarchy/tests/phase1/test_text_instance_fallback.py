"""Recover instances dropped by partial pyslang parse (unified_verify hfa)."""

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

MIDDLE = hfa_rtl_dir() / "middle_module.v"


def test_scan_finds_parametric_instance():
    from hch.ingest.text_instance_fallback import (
        apply_ifdef_filter,
        extract_module_body,
        scan_hierarchy_instances,
    )

    raw = MIDDLE.read_text(encoding="utf-8")
    body = extract_module_body(apply_ifdef_filter(raw, {}), "middle_module")
    pairs = scan_hierarchy_instances(body)
    names = {inst for _mod, inst in pairs}
    assert "u_subTop_0" in names
    assert "u_sub_1" in names
    assert "u_sub_2" not in names


@pytest.mark.requires_engine
def test_ingest_recovers_u_subtop_0():
    from hch.engine.availability import check_engine
    from hch.ingest.hierarchy_build import elaborate_flat
    from hch.ingest.ingest import ingest_filelist, get_last_parse_meta

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not unified_filelist().exists():
        pytest.skip(f"missing {unified_filelist()}")

    mods = ingest_filelist(unified_filelist(), index_cwd=str(unified_verify_dir()))
    meta = get_last_parse_meta()
    assert int(meta.get("text_fallback_instance_count", "0")) >= 1

    mid = mods["middle_module"]
    insts = {e.inst_name for e in mid.instances}
    assert "u_subTop_0" in insts
    assert "u_sub_1" in insts
    assert "u_sub_2" not in insts

    flat = elaborate_flat(mods, top_module="top_module")
    paths = {f.full_path for f in flat}
    assert "top_module.u_middle_0.u_subTop_0" in paths
    assert "top_module.u_middle_0.u_sub_1" in paths


@pytest.mark.requires_engine
def test_index_meta_records_text_fallback(tmp_path):
    from hch.engine.availability import check_engine
    from hch.index.loader import build_index_from_filelist

    status = check_engine()
    if not status.available:
        pytest.skip(status.message)
    if not unified_filelist().exists():
        pytest.skip(f"missing {unified_filelist()}")

    db = tmp_path / "fb.hch.db"
    store = build_index_from_filelist(
        str(unified_filelist()),
        str(db),
        top_module="top_module",
        index_cwd=str(unified_verify_dir()),
    )
    assert int(store.get_meta("text_fallback_instance_count") or "0") >= 1
    rows = store.export_instance_dicts()
    store.close()
    paths = {r["name"] for r in rows}
    assert "top_module.u_middle_0.u_subTop_0" in paths