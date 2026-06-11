"""Conditional depth: anchor path globs vs shallow parse."""

from __future__ import annotations

from pathlib import Path

import pytest

from hch.ingest.parse_depth import (
    ConditionalDepthPolicy,
    classify_parse_sources_conditional,
    path_matches_anchor,
    select_parse_sources_conditional,
)


def test_path_matches_anchor_globs():
    legacy = ConditionalDepthPolicy.from_sequences(["*_top*"])
    assert path_matches_anchor("top.u_cpu", "", legacy, module_name="cpu_top")
    assert path_matches_anchor("soc_top.u_periph", "", legacy) is False
    assert path_matches_anchor(
        "top.u_axi", "", ConditionalDepthPolicy.from_sequences(["*_grp*"]), module_name="axi_grp"
    )
    assert path_matches_anchor(
        "top.u_log", "", ConditionalDepthPolicy.from_sequences(["*_log*"]), module_name="log_ctrl"
    )


def test_path_matches_anchor_inst_vs_module():
    # inst u_ct under module cpu_top — module-only anchor must match, inst-only must not
    policy_mod = ConditionalDepthPolicy.from_sequences(anchor_module_patterns=["*_top*"])
    assert path_matches_anchor("soc.u_cpu.u_ct", "", policy_mod, module_name="cpu_top")
    assert not path_matches_anchor("soc.u_cpu.u_ct", "", policy_mod, module_name="cpu_wrap")

    policy_inst = ConditionalDepthPolicy.from_sequences(anchor_inst_patterns=["u_ct"])
    assert path_matches_anchor("soc.u_cpu.u_ct", "", policy_inst, module_name="cpu_top")
    assert not path_matches_anchor("soc.u_cpu.u_x", "", policy_inst, module_name="cpu_top")

    # inst name u_cpu_top but module wrap — only legacy/inst catches inst leaf
    policy_inst_glob = ConditionalDepthPolicy.from_sequences(anchor_inst_patterns=["*_top*"])
    assert path_matches_anchor("soc.u_cpu_top", "", policy_inst_glob, module_name="wrap")
    assert not path_matches_anchor(
        "soc.u_cpu", "", policy_inst_glob, module_name="cpu_top"
    )


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


def test_anchor_extra_depth_limits_parse_files(tmp_path: Path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "soc.v").write_text(
        "module soc;\n  cpu_wrap u_cpu ();\n  dma_wrap u_dma ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "cpu_wrap.v").write_text(
        "module cpu_wrap;\n  cpu_top u_ct ();\nendmodule\n",
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
    (rtl / "leaf.v").write_text(
        "module leaf;\n  deep u_d ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "deep.v").write_text("module deep;\nendmodule\n", encoding="utf-8")
    (rtl / "dma_wrap.v").write_text(
        "module dma_wrap;\n  dma_top u_dt ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "dma_top.v").write_text(
        "module dma_top;\n  fifo u_f ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "fifo.v").write_text("module fifo;\nendmodule\n", encoding="utf-8")
    sources = [str(p.resolve()) for p in sorted(rtl.glob("*.v"))]
    policy = ConditionalDepthPolicy.from_sequences(
        ["*_top*"],
        shallow_depth=1,
        anchor_extra_depth=2,
    )
    full, skim = classify_parse_sources_conditional("soc", sources, policy)
    resolved = {str(Path(s).resolve()) for s in sources}
    assert str(rtl / "cpu_top.v") in full
    assert str(rtl / "core.v") in full
    assert str(rtl / "leaf.v") in full
    assert str(rtl / "deep.v") not in full
    assert str(rtl / "deep.v") not in skim
    assert str(rtl / "dma_top.v") in full
    assert str(rtl / "fifo.v") in full


@pytest.mark.requires_engine
def test_index_anchor_module_extra_depth(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "soc.v").write_text(
        "module soc;\n  cpu_wrap u_cpu ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "cpu_wrap.v").write_text(
        "module cpu_wrap;\n  cpu_top u_ct ();\nendmodule\n",
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
    fl = tmp_path / "soc.f"
    fl.write_text(
        "\n".join(str(rtl / n) for n in ["soc.v", "cpu_wrap.v", "cpu_top.v", "core.v", "leaf.v"])
        + "\n"
    )
    db = tmp_path / "mod_anchor.hch.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="soc",
        batch_size=8,
        depth_anchor_module_patterns=["*_top*"],
        depth_shallow=1,
        depth_anchor_extra=1,
    ).close()

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "soc.u_cpu.u_ct" in paths
        assert "soc.u_cpu.u_ct.u_c" in paths
        assert "soc.u_cpu.u_ct.u_c.u_l" not in paths
    finally:
        store.close()


@pytest.mark.requires_engine
def test_index_anchor_extra_depth_two_branches(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "soc.v").write_text(
        "module soc;\n  cpu_wrap u_cpu ();\n  dma_wrap u_dma ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "cpu_wrap.v").write_text(
        "module cpu_wrap;\n  cpu_top u_ct ();\nendmodule\n",
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
    (rtl / "leaf.v").write_text(
        "module leaf;\n  deep u_d ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "deep.v").write_text("module deep;\nendmodule\n", encoding="utf-8")
    (rtl / "dma_wrap.v").write_text(
        "module dma_wrap;\n  dma_top u_dt ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "dma_top.v").write_text(
        "module dma_top;\n  fifo u_f ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "fifo.v").write_text("module fifo;\nendmodule\n", encoding="utf-8")
    fl = tmp_path / "soc.f"
    fl.write_text("\n".join(str(rtl / n) for n in sorted(x.name for x in rtl.glob("*.v"))) + "\n")
    db = tmp_path / "anchor_extra.hch.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="soc",
        batch_size=8,
        depth_anchor_patterns=["*_top*"],
        depth_shallow=1,
        depth_anchor_extra=2,
    ).close()

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "soc.u_cpu.u_ct" in paths
        assert "soc.u_cpu.u_ct.u_c" in paths
        assert "soc.u_cpu.u_ct.u_c.u_l" in paths
        assert "soc.u_cpu.u_ct.u_c.u_l.u_d" not in paths
        assert "soc.u_dma.u_dt" in paths
        assert "soc.u_dma.u_dt.u_f" in paths
        assert store.get_meta("depth_anchor_extra") == "2"
    finally:
        store.close()


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