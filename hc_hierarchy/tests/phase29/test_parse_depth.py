"""--max-depth parse and flatten limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from hch.ingest.hierarchy_build import elaborate_flat
from hch.ingest.parse_depth import select_parse_sources_by_depth
from hch.schema import InstanceEdge, ModuleRecord


def _mod(name: str, kids: list[tuple[str, str]], path: str = "") -> ModuleRecord:
    return ModuleRecord(
        module_name=name,
        file_path=path or f"/rtl/{name}.v",
        instances=[
            InstanceEdge(
                parent_module=name,
                inst_name=inst,
                child_module=child,
                file_path=path or f"/rtl/{name}.v",
            )
            for child, inst in kids
        ],
    )


def test_select_parse_sources_depth_0(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.v").write_text(
        "module top;\n  mid u_m ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "mid.v").write_text(
        "module mid;\n  leaf u_l ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    sources = [str(rtl / "top.v"), str(rtl / "mid.v"), str(rtl / "leaf.v")]
    allowed = select_parse_sources_by_depth("top", sources, 0)
    assert allowed == {str(rtl / "top.v")}


def test_select_parse_sources_depth_1(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.v").write_text(
        "module top;\n  mid u_m ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "mid.v").write_text(
        "module mid;\n  leaf u_l ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    sources = [str(rtl / "top.v"), str(rtl / "mid.v"), str(rtl / "leaf.v")]
    allowed = select_parse_sources_by_depth("top", sources, 1)
    assert allowed == {str(rtl / "top.v"), str(rtl / "mid.v")}


def test_elaborate_flat_max_depth():
    mods = {
        "top": _mod("top", [("mid", "u_m")]),
        "mid": _mod("mid", [("leaf", "u_l")]),
        "leaf": _mod("leaf", []),
    }
    flat = elaborate_flat(mods, top_module="top", max_depth=1)
    paths = {r.full_path for r in flat}
    assert "top" in paths
    assert "top.u_m" in paths
    assert not any(p.startswith("top.u_m.") for p in paths)


@pytest.mark.requires_engine
def test_index_max_depth_integration(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.v").write_text(
        "module top;\n  mid u_m ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "mid.v").write_text(
        "module mid;\n  leaf u_l ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    fl = tmp_path / "top.f"
    fl.write_text(
        f"{rtl / 'top.v'}\n{rtl / 'mid.v'}\n{rtl / 'leaf.v'}\n",
        encoding="utf-8",
    )
    db = tmp_path / "depth.hch.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="top",
        batch_size=8,
        max_depth=1,
    ).close()

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_m" in paths
        assert not any(p.startswith("top.u_m.") for p in paths)
        assert store.get_meta("index_max_depth") == "1"
        assert "leaf" not in store.load_all_modules()
    finally:
        store.close()