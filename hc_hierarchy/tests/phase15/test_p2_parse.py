"""Phase 15 (P2): port connect, defparam, primitive, filelist meta, inst_json round-trip."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
P2 = ROOT / "design" / "extras" / "parse_p2"


def _resolve_filelist(name: str) -> str:
    fl = P2 / name
    text = fl.read_text(encoding="utf-8")
    text = text.replace("${HCH_ROOT}", str(ROOT))
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"hch_{name}"
    out.write_text(text, encoding="utf-8")
    return str(out)


@pytest.mark.requires_engine
def test_port_connections_and_primitive():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    src = P2 / "rtl" / "p2_features.v"
    trees = parse_syntax_trees([src])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(src))}
    top = mods["top"]
    g1 = next(e for e in top.instances if e.inst_name == "g1")
    assert g1.child_type
    assert g1.port_connections
    assert any("a" in v for v in g1.port_connections.values())
    assert mods.get("and") or any(e.child_module == "and" for e in top.instances)
    u = next(e for e in top.instances if e.inst_name == "u")
    assert u.port_connections.get("clk")


@pytest.mark.requires_engine
def test_defparam_in_parameters():
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees, get_last_extract_stats

    src = P2 / "rtl" / "defparam_top.v"
    trees = parse_syntax_trees([src])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(src))}
    assert "u.child.P" in mods["defparam_top"].parameters
    assert get_last_extract_stats().get("defparam_count", 0) >= 1


@pytest.mark.requires_engine
def test_index_p2_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "p2.hch.db"
    store = build_index_from_filelist(
        _resolve_filelist("filelist.f"),
        str(db),
        top_module="top",
        filelist_diff=_resolve_filelist("filelist_alt.f"),
    )
    assert store.get_meta("defparam_count", "0") != "0" or store.get_meta("primitive_count", "0") != "0"
    assert store.get_meta("port_connection_edge_count", "0") != "0"
    unsup = store.get_meta("unsupported_filelist_opts_json", "[]")
    assert "+ntb" in unsup
    diff = json.loads(store.get_meta("filelist_diff_json", "{}"))
    assert diff.get("only_primary_sources")
    badge_src = store.get_meta("hierarchy_source", "")
    store.close()
    assert badge_src in ("ast", "path", "elab", "tier_p_fallback", "elab_partial")


@pytest.mark.requires_engine
def test_inst_json_round_trip(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "rt.hch.db"
    store = build_index_from_filelist(
        _resolve_filelist("filelist.f"),
        str(db),
        top_module="top",
    )
    mods = store.load_all_modules()
    top = mods["top"]
    u = next(e for e in top.instances if e.inst_name == "u")
    assert u.port_connections
    store.close()


@pytest.mark.requires_engine
def test_flatten_cycle_warning():
    from hch.ingest.hierarchy_build import elaborate_flat, flatten_cycle_detected
    from hch.schema import InstanceEdge, ModuleRecord

    a = ModuleRecord(
        module_name="a",
        file_path="",
        instances=[
            InstanceEdge(
                parent_module="a",
                inst_name="u",
                child_module="b",
                file_path="",
            )
        ],
    )
    b = ModuleRecord(
        module_name="b",
        file_path="",
        instances=[
            InstanceEdge(
                parent_module="b",
                inst_name="u",
                child_module="a",
                file_path="",
            )
        ],
    )
    elaborate_flat({"a": a, "b": b}, top_module="a")
    assert flatten_cycle_detected()


@pytest.mark.requires_engine
def test_api_parse_tier_badge(tmp_path):
    from hch.apps.api.db_service import HierarchyDbService
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "api.hch.db"
    build_index_from_filelist(
        _resolve_filelist("filelist.f"),
        str(db),
        top_module="top",
    ).close()
    svc = HierarchyDbService(str(db))
    meta = svc.meta()
    svc.close()
    assert "parse_tier_badge" in meta
    assert "Tier" in meta["parse_tier_badge"]