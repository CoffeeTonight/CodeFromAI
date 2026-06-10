"""Conditional depth: anchor path globs vs shallow parse."""

from __future__ import annotations

from pathlib import Path

import pytest

from hch.ingest.parse_depth import (
    ConditionalDepthPolicy,
    path_matches_anchor,
    select_parse_sources_conditional,
)


def test_path_matches_anchor_globs():
    assert path_matches_anchor("top.u_cpu", "", ["*_top*"], module_name="cpu_top")
    assert path_matches_anchor("soc_top.u_periph", "", ["*_top*"]) is False
    assert path_matches_anchor("top.u_axi", "", ["*_grp*"], module_name="axi_grp")
    assert path_matches_anchor("top.u_log", "", ["*_log*"], module_name="log_ctrl")


def test_conditional_parse_shallow_branch(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.v").write_text(
        "module top;\n  cpu_top u_cpu ();\n  periph u_p ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "cpu_top.v").write_text(
        "module cpu_top;\n  core u_c ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "core.v").write_text(
        "module core;\n  leaf u_l ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    (rtl / "periph.v").write_text(
        "module periph;\n  regfile u_r ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "regfile.v").write_text(
        "module regfile;\n  leaf u_b ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    sources = [str(p.resolve()) for p in rtl.glob("*.v")]
    policy = ConditionalDepthPolicy.from_sequences(
        ["*_top*", "*_grp*", "*_log*"],
        shallow_depth=2,
    )
    allowed = select_parse_sources_conditional("top", sources, policy)
    # anchor branch: top, cpu_top, core, leaf
    assert str(rtl / "cpu_top.v") in allowed
    assert str(rtl / "core.v") in allowed
    assert str(rtl / "leaf.v") in allowed
    # shallow branch: periph + 2 descendant levels (regfile, bit)
    assert str(rtl / "periph.v") in allowed
    assert str(rtl / "regfile.v") in allowed
    assert str(rtl / "leaf.v") in allowed


@pytest.mark.requires_engine
def test_index_conditional_depth(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "top.v").write_text(
        "module top;\n  periph u_p ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "periph.v").write_text(
        "module periph;\n  regfile u_r ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "regfile.v").write_text(
        "module regfile;\n  leaf u_b ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    fl = tmp_path / "top.f"
    fl.write_text("\n".join(str(rtl / n) for n in ["top.v", "periph.v", "regfile.v", "leaf.v"]) + "\n")
    db = tmp_path / "cond.hch.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="top",
        batch_size=8,
        depth_anchor_patterns=["*_top*"],
        depth_shallow=2,
    ).close()

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_p" in paths
        assert "top.u_p.u_r" in paths
        assert "top.u_p.u_r.u_b" in paths
        assert "leaf" in store.load_all_modules()
    finally:
        store.close()