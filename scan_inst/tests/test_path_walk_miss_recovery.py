"""Path-walk: deferred miss logging + full walk targets after partial prefix walks."""

from __future__ import annotations

import io
from pathlib import Path

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import (
    _inst_path_from_spec,
    _walk_target_from_spec,
    build_path_walk_state,
    create_path_walk_index,
    run_path_walk_connect,
)


def _write_dup_blk_chain(tmp_path: Path) -> tuple[Path, str]:
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
    fl = tmp_path / "design.f"
    fl.write_text(
        "\n".join(
            str((tmp_path / n).resolve())
            for n in ("top.v", "blk_stub.v", "blk_real.v", "core.v", "leaf.v")
        )
        + "\n",
        encoding="utf-8",
    )
    return fl, "SOC_TOP.u_blk.u_core.u_leaf"


def test_walk_target_is_full_spec_not_truncated_prefix(tmp_path: Path):
    fl_path, leaf = _write_dup_blk_chain(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    index, mod_db = create_path_walk_index(fl, "SOC_TOP", defines={}, no_cache=True)
    from scan_inst.path_walk import PathWalkState

    state = PathWalkState(index=index, top="SOC_TOP", mod_db=mod_db)
    state.ensure_root()
    state.ensure_path("SOC_TOP.u_blk")
    # Partial walk stopped before u_core (as after an earlier failed prefix attempt).

    assert _walk_target_from_spec(leaf, state) == leaf
    assert _inst_path_from_spec(leaf, state) == "SOC_TOP.u_blk.u_core"


def test_recovered_walk_does_not_leave_stale_miss_in_trace(tmp_path: Path):
    fl_path, leaf = _write_dup_blk_chain(tmp_path)
    fl = parse_filelist(str(fl_path), index_cwd=str(tmp_path))
    buf = io.StringIO()
    request = ConnectivityRequest(
        checks=(ConnectivityCheck(leaf, leaf),),
        top="SOC_TOP",
    )
    batch, _, state = run_path_walk_connect(
        request,
        fl,
        top="SOC_TOP",
        no_cache=True,
        trace_stream=buf,
    )
    assert leaf in state.rows_by_path
    assert batch.results[0].connected is True
    text = buf.getvalue()
    assert "ok " + leaf in text
    assert "miss inst=" not in text