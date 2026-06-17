"""Path-walk trie dedup and branch-point helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import (
    _path_trie_branch_points,
    _path_trie_from_specs,
    _sorted_unique_specs,
    run_path_walk_connect,
)


def test_sorted_unique_specs_dedups_and_orders():
    specs = [
        "top.b.a",
        "top.a",
        "top.b.a",
        "top.a.z",
    ]
    assert _sorted_unique_specs(specs) == ["top.a", "top.a.z", "top.b.a"]


def test_path_trie_branch_points():
    root = _path_trie_from_specs(
        [
            "top.u_soc.u_cpusystem.b",
            "top.u_soc.u_ifdef.c",
            "top.u_soc.u_mid.x",
        ],
        top="top",
    )
    branches = _path_trie_branch_points(root)
    assert branches == ["top.u_soc"]


def test_walk_fewer_target_calls_with_duplicate_specs(tmp_path: Path):
    rtl = tmp_path / "d.v"
    rtl.write_text(
        """
    module top(input wire_a, input wire_b, input wire_c);
      wire [2:0] bus_out;
      assign bus_out[0] = wire_a;
      assign bus_out[1] = wire_b;
      assign bus_out[2] = wire_c;
    endmodule
    """,
        encoding="utf-8",
    )
    fl = tmp_path / "f.f"
    fl.write_text(str(rtl.resolve()) + "\n", encoding="utf-8")
    fl_res = parse_filelist(str(fl), index_cwd=str(tmp_path))
    checks = tuple(
        ConnectivityCheck("top.bus_out[0]", "top.wire_a", f"n{i}")
        for i in range(20)
    )
    request = ConnectivityRequest(checks=checks, top="top")
    batch, _index, state = run_path_walk_connect(request, fl_res, top="top")
    assert len(batch.results) == 20
    assert all(r.connected for r in batch.results)
    assert state.stats.endpoint_specs_raw == 40
    assert state.stats.endpoint_specs_unique == 2
    assert state.stats.walk_target_calls == 2
    assert state.stats.walk_target_skipped >= 0