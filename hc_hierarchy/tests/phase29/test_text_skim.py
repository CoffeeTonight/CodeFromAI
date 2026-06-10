"""Text-skim ingest and tiered conditional-depth classification."""

from __future__ import annotations

from pathlib import Path

import pytest

from hch.ingest.parse_depth import (
    ConditionalDepthPolicy,
    classify_parse_sources_conditional,
)
from hch.ingest.text_skim import ingest_sources_text_skim


def _fixture_sources(tmp_path: Path) -> tuple[Path, list[str]]:
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
    sources = [str(p.resolve()) for p in rtl.glob("*.v")]
    return rtl, sources


def test_classify_parse_tiers(tmp_path: Path):
    rtl, sources = _fixture_sources(tmp_path)
    policy = ConditionalDepthPolicy.from_sequences(
        ["*_top*", "*_grp*", "*_log*"],
        shallow_depth=2,
    )
    full_set, skim_set = classify_parse_sources_conditional("top", sources, policy)
    assert str(rtl / "top.v") in full_set | skim_set
    assert str(rtl / "cpu_top.v") in full_set
    assert str(rtl / "core.v") in full_set
    assert str(rtl / "leaf.v") in full_set
    assert str(rtl / "periph.v") in skim_set
    assert str(rtl / "regfile.v") in skim_set
    assert str(rtl / "periph.v") not in full_set
    assert str(rtl / "leaf.v") not in skim_set


def test_text_skim_extracts_instances(tmp_path: Path):
    rtl, sources = _fixture_sources(tmp_path)
    skim_paths = [str(rtl / "periph.v"), str(rtl / "regfile.v")]
    mods = ingest_sources_text_skim(skim_paths)
    assert "periph" in mods
    assert "regfile" in mods
    periph_edges = {(e.inst_name, e.child_module) for e in mods["periph"].instances}
    assert ("u_r", "regfile") in periph_edges
    assert all(e.child_kind == "text_skim" for e in mods["periph"].instances)


@pytest.mark.requires_engine
def test_index_skim_parse_meta(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    rtl, _ = _fixture_sources(tmp_path)
    fl = tmp_path / "top.f"
    fl.write_text(
        "\n".join(
            str(rtl / n)
            for n in ["top.v", "cpu_top.v", "core.v", "leaf.v", "periph.v", "regfile.v"]
        )
        + "\n",
        encoding="utf-8",
    )
    db = tmp_path / "skim.hch.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="top",
        batch_size=8,
        depth_anchor_patterns=["*_top*"],
        depth_shallow=2,
        skim_parse=True,
    ).close()

    store = HierarchyStore(str(db))
    try:
        assert store.get_meta("index_skim_parse") == "1"
        assert int(store.get_meta("parse_skim_count") or "0") >= 2
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_p" in paths
        assert "top.u_p.u_r" in paths
        assert "top.u_cpu.u_c" in paths
        rows = store.export_instance_dicts()
        skim_paths = {r["name"] for r in rows if r.get("parse_tier") == "skim"}
        assert any("u_p" in p for p in skim_paths)
    finally:
        store.close()