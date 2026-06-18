"""Confident (child filelist) vs recovery (subtree/global) resolve policy."""

from __future__ import annotations

import io
from pathlib import Path

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import run_path_walk_connect
from scan_inst.path_walk_db import RESOLVE_CONFIDENT, RESOLVE_RECOVERY


def _write_nested_child_fl_design(tmp_path: Path) -> Path:
    (tmp_path / "top.v").write_text(
        "module SOC_TOP; BLK u_blk (); endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "blk_real.v").write_text(
        "module BLK; CORE u_core (); endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "core.v").write_text(
        "module CORE; LEAF u_leaf (); endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "leaf.v").write_text("module LEAF; endmodule\n", encoding="utf-8")
    lists = tmp_path / "lists"
    lists.mkdir()
    (lists / "child.f").write_text(
        "\n".join(
            str((tmp_path / n).resolve())
            for n in ("blk_real.v", "core.v", "leaf.v")
        )
        + "\n",
        encoding="utf-8",
    )
    (lists / "parent.f").write_text(
        "\n".join(
            [
                str((tmp_path / "top.v").resolve()),
                f"-f {(lists / 'child.f').resolve()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    root = tmp_path / "root.f"
    root.write_text(f"-f {(lists / 'parent.f').resolve()}\n", encoding="utf-8")
    return root


def _write_stub_child_recovery_design(tmp_path: Path) -> tuple[Path, str]:
    (tmp_path / "top.v").write_text(
        "module SOC_TOP; BLK u_blk (); endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "blk_stub.v").write_text("module BLK; endmodule\n", encoding="utf-8")
    (tmp_path / "blk_real.v").write_text(
        "module BLK; CORE u_core (); endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "core.v").write_text(
        "module CORE; LEAF u_leaf (); endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "leaf.v").write_text("module LEAF; endmodule\n", encoding="utf-8")
    lists = tmp_path / "lists"
    lists.mkdir()
    (lists / "child.f").write_text(
        str((tmp_path / "blk_stub.v").resolve()) + "\n",
        encoding="utf-8",
    )
    (lists / "parent.f").write_text(
        "\n".join(
            [
                str((tmp_path / "top.v").resolve()),
                f"-f {(lists / 'child.f').resolve()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    root = tmp_path / "root.f"
    root.write_text(
        "\n".join(
            [
                f"-f {(lists / 'parent.f').resolve()}",
                str((tmp_path / "blk_real.v").resolve()),
                str((tmp_path / "core.v").resolve()),
                str((tmp_path / "leaf.v").resolve()),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return root, "SOC_TOP.u_blk.u_core.u_leaf"


def test_confident_resolves_module_in_direct_child_filelist(tmp_path: Path):
    fl_path = _write_nested_child_fl_design(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    from scan_inst.path_walk import create_path_walk_index

    index, mod_db = create_path_walk_index(fl, "SOC_TOP", defines={}, no_cache=True)
    assert mod_db.resolve_child_edge(
        "SOC_TOP",
        {},
        "u_blk",
        current_file=str((tmp_path / "top.v").resolve()),
        policy=RESOLVE_CONFIDENT,
    ) is not None


def test_confident_defers_then_recovery_walks_full_chain(tmp_path: Path):
    fl_path, leaf = _write_stub_child_recovery_design(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    buf = io.StringIO()
    req = ConnectivityRequest(
        checks=(ConnectivityCheck(leaf, leaf),),
        top="SOC_TOP",
    )
    batch, _index, state = run_path_walk_connect(
        req,
        fl,
        top="SOC_TOP",
        no_cache=True,
        trace_stream=buf,
    )
    text = buf.getvalue()
    assert "confident-miss defer" in text
    assert "recovery-pass start" in text
    assert leaf in state.rows_by_path
    assert batch.results[0].connected is True