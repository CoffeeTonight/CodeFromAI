"""On-demand branch deepen (pyslang)."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_shallow_index(tmp_path: Path) -> tuple[Path, Path]:
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
    (rtl / "deep.v").write_text(
        "module deep;\n  inner u_i ();\nendmodule\n",
        encoding="utf-8",
    )
    (rtl / "inner.v").write_text("module inner;\nendmodule\n", encoding="utf-8")
    fl = tmp_path / "top.f"
    fl.write_text(
        "\n".join(
            str(rtl / n)
            for n in [
                "top.v",
                "periph.v",
                "regfile.v",
                "leaf.v",
                "deep.v",
                "inner.v",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    db = tmp_path / "shallow.hch.db"
    return fl, db


@pytest.mark.requires_engine
def test_deepen_expands_shallow_branch(tmp_path: Path):
    from hch.index.deepen import deepen_branch
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    fl, db = _write_shallow_index(tmp_path)
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="top",
        batch_size=8,
        depth_anchor_patterns=["*_top*"],
        depth_shallow=1,
        skim_parse=True,
    ).close()

    store = HierarchyStore(str(db))
    try:
        before = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_p" in before
        assert "top.u_p.u_r" in before
        assert "top.u_p.u_r.u_b" not in before
    finally:
        store.close()

    result = deepen_branch(str(db), "top.u_p", full_subtree=True)
    assert result.instances_after > result.instances_before

    store = HierarchyStore(str(db))
    try:
        after = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_p.u_r.u_b" in after
        deepened = store.get_meta("deepened_paths_json")
        assert "top.u_p" in (deepened or "")
    finally:
        store.close()


def test_tier_can_deepen():
    from hch.apps.gui.main_window import tier_can_deepen

    assert tier_can_deepen("skim") is True
    assert tier_can_deepen("shallow_cap") is True
    assert tier_can_deepen("full") is False
    assert tier_can_deepen("") is False


@pytest.mark.requires_engine
def test_deepen_cli(tmp_path: Path, capsys):
    from hch.apps.deepen_cli import main
    from hch.index.loader import build_index_from_filelist
    from hch.index.store import HierarchyStore

    fl, db = _write_shallow_index(tmp_path)
    build_index_from_filelist(
        str(fl),
        str(db),
        top_module="top",
        batch_size=8,
        depth_anchor_patterns=["*_none*"],
        depth_shallow=1,
        skim_parse=True,
    ).close()

    rc = main(["-d", str(db), "--under", "top.u_p", "--full"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "Deepened" in err

    store = HierarchyStore(str(db))
    try:
        paths = {r["name"] for r in store.export_instance_dicts()}
        assert "top.u_p.u_r" in paths
    finally:
        store.close()