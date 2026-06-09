"""Recover instances dropped by partial pyslang parse (HDLforAST)."""

from pathlib import Path

import pytest

from hch.paths import design_dir

DESIGN = design_dir("HDLforAST")
FILELIST = DESIGN / "filelist.f"
MIDDLE = DESIGN / "middle_module.v"


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
    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    mods = ingest_filelist(FILELIST, index_cwd=str(DESIGN))
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
    if not FILELIST.exists():
        pytest.skip(f"missing {FILELIST}")

    db = tmp_path / "fb.hch.db"
    store = build_index_from_filelist(
        str(FILELIST),
        str(db),
        top_module="top_module",
        index_cwd=str(DESIGN),
    )
    assert int(store.get_meta("text_fallback_instance_count") or "0") >= 1
    rows = store.export_instance_dicts()
    store.close()
    paths = {r["name"] for r in rows}
    assert "top_module.u_middle_0.u_subTop_0" in paths