"""Path-based IP blackbox indexing (--blackbox-path)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hch.ingest.kit_blackbox import (
    partition_sources,
    resolve_blackbox_path_patterns,
    scan_kit_blackbox_modules,
)


def test_resolve_blackbox_path_patterns():
    assert resolve_blackbox_path_patterns(["vendor_ip"]) == ["vendor_ip"]
    assert resolve_blackbox_path_patterns(["a", "b"]) == ["a", "b"]
    assert resolve_blackbox_path_patterns([]) == []


def test_resolve_blackbox_path_patterns_from_env(monkeypatch):
    monkeypatch.setenv("HCH_BLACKBOX_PATH", "dk_rtl, vendor_ip")
    assert resolve_blackbox_path_patterns(["extra"]) == ["dk_rtl", "vendor_ip", "extra"]


def test_partition_sources_by_substring():
    sources = [
        "/soc/rtl/top.v",
        "/soc/vendor_ip/ip/sub.v",
        "/soc/rtl/cpu.v",
    ]
    parse, kit = partition_sources(sources, ["vendor_ip"])
    assert parse == ["/soc/rtl/top.v", "/soc/rtl/cpu.v"]
    assert kit == ["/soc/vendor_ip/ip/sub.v"]


def test_scan_kit_blackbox_modules(tmp_path: Path):
    ip = tmp_path / "vendor_ip"
    ip.mkdir()
    (ip / "dk_cell.v").write_text(
        "module dk_cell;\n  dk_inner u0();\nendmodule\n",
        encoding="utf-8",
    )
    mods = scan_kit_blackbox_modules([str(ip / "dk_cell.v")])
    assert "dk_cell" in mods
    assert mods["dk_cell"].is_blackbox is True
    assert mods["dk_cell"].parse_tier == "blackbox"
    assert len(mods["dk_cell"].instances) >= 1


@pytest.mark.requires_engine
def test_unified_verify_hfa_blackbox_orphan_tree(tmp_path: Path):
    """filelist.f + --blackbox-path hfa: hc_verify_top + top_module blackbox subtree."""
    from pathlib import Path as P

    repo = P(__file__).resolve().parents[2]
    fl = repo / "design/unified_verify/filelist.f"
    if not fl.is_file():
        pytest.skip("unified_verify fixture missing")
    db = tmp_path / "uv_bb.hch.db"
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    build_index_from_filelist(
        str(fl),
        str(db),
        index_cwd=str(repo / "design/unified_verify"),
        blackbox_paths=["hfa"],
        jobs=4,
    ).close()

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "hc_verify_top" in paths
        assert "top_module" in paths
        assert any(p.startswith("top_module.u_middle") for p in paths)
        tags = store.conn.execute(
            "SELECT inst_tags_json FROM instances WHERE full_path = 'top_module' LIMIT 1"
        ).fetchone()[0]
        assert "blackbox" in (tags or "")
        assert int(store.get_meta("kit_blackbox_source_count", "0")) >= 4
    finally:
        store.close()


@pytest.mark.requires_engine
def test_index_blackbox_path_skips_inner_hierarchy(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    rtl = tmp_path / "rtl"
    ip = tmp_path / "my_dk_folder"
    rtl.mkdir()
    ip.mkdir()
    (rtl / "top.v").write_text(
        "module top;\n  dk_cell u_dk ();\nendmodule\n",
        encoding="utf-8",
    )
    (ip / "dk_cell.v").write_text(
        "module dk_cell;\n  dk_inner u_in ();\nendmodule\n",
        encoding="utf-8",
    )
    (ip / "dk_inner.v").write_text(
        "module dk_inner;\nendmodule\n",
        encoding="utf-8",
    )
    fl = tmp_path / "top.f"
    fl.write_text(
        f"{rtl / 'top.v'}\n{ip / 'dk_cell.v'}\n{ip / 'dk_inner.v'}\n",
        encoding="utf-8",
    )
    db = tmp_path / "kit.hch.db"

    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="top",
        batch_size=8,
        blackbox_paths=["my_dk_folder"],
    ).close()

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_dk" in paths
        assert not any(p.startswith("top.u_dk.") for p in paths)
        assert int(store.get_meta("kit_blackbox_source_count", "0")) == 2
        mods = store.load_all_modules()
        assert mods["dk_cell"].parse_tier == "blackbox"
        assert mods["dk_inner"].parse_tier == "blackbox"
        assert "my_dk_folder" in store.get_meta("kit_blackbox_patterns_json", "")
    finally:
        store.close()