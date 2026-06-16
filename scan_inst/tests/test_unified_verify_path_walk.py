"""Path-walk integration on hc_hierarchy unified_verify corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.cone import fanout_cone
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import (
    build_path_walk_state_from_specs,
    create_path_walk_index,
    run_path_walk_connect,
    run_path_walk_index,
)

_CANDIDATE_ROOTS = (
    Path("/home/user/tools/__CFI/hc_hierarchy/design/unified_verify"),
    Path("/home/user/tools/CodeFromAI/hc_hierarchy/design/unified_verify"),
)

UNIFIED_VERIFY = next((p for p in _CANDIDATE_ROOTS if (p / "filelist.f").is_file()), None)
FILELIST = UNIFIED_VERIFY / "filelist.f" if UNIFIED_VERIFY else None
TOP = "hc_verify_top"


@pytest.mark.skipif(FILELIST is None, reason="unified_verify corpus not available")
def test_unified_verify_anchor_depth_chain_path_walk():
    fl = parse_filelist(str(FILELIST), index_cwd=str(UNIFIED_VERIFY))
    index, mod_db = create_path_walk_index(fl, TOP, defines=dict(fl.defines), no_cache=True)
    paths = [
        f"{TOP}.u_anchor_flat.u_chain.u_d2.u_d3",
        f"{TOP}.u_anchor_flat.u_chain.u_d2.u_d3.u_l",
        f"{TOP}.u_anchor_nested.u_inner.u_chain.u_d2.u_d3",
    ]
    state = build_path_walk_state_from_specs(index, TOP, paths, mod_db)
    for path in paths:
        assert path in state.rows_by_path, path
        row = state.rows_by_path[path]
        assert row.file.endswith("mid_anchor_depth.v")


@pytest.mark.skipif(FILELIST is None, reason="unified_verify corpus not available")
def test_unified_verify_ifdef_instance_under_define():
    fl = parse_filelist(str(FILELIST), index_cwd=str(UNIFIED_VERIFY))
    assert "USE_M1" in fl.defines
    index, mod_db = create_path_walk_index(fl, TOP, defines=dict(fl.defines), no_cache=True)
    state = build_path_walk_state_from_specs(
        index, TOP, [f"{TOP}.u_ifdef.u_mid_1"], mod_db,
    )
    assert f"{TOP}.u_ifdef.u_mid_1" in state.rows_by_path


@pytest.mark.skipif(FILELIST is None, reason="unified_verify corpus not available")
def test_unified_verify_idx_connect_path_walk():
    fl = parse_filelist(str(FILELIST), index_cwd=str(UNIFIED_VERIFY))
    request = ConnectivityRequest(
        checks=(
            ConnectivityCheck(
                f"{TOP}.idx",
                f"{TOP}.u_ecc_engine_00.idx",
                check_id="idx",
            ),
        ),
        top=TOP,
    )
    batch, _index, state = run_path_walk_connect(
        request, fl, top=TOP, no_cache=True,
    )
    assert batch.results[0].connected is True
    assert f"{TOP}.u_ecc_engine_00" in state.rows_by_path


@pytest.mark.skipif(FILELIST is None, reason="unified_verify corpus not available")
def test_unified_verify_generate_fanout_cone_path_walk():
    """if-generate instance (gen_on.u_on) needs filelist +define+ENABLE for cone fold."""
    fl = parse_filelist(str(FILELIST), index_cwd=str(UNIFIED_VERIFY))
    endpoint = f"{TOP}.u_gen_if.gen_on.u_on.done"
    index, state, top = run_path_walk_index(
        fl,
        [endpoint],
        top=TOP,
        no_cache=True,
    )
    result = fanout_cone(
        endpoint,
        rows=state.rows(),
        index=index,
        top=top,
        defines=dict(fl.defines),
    )
    assert not result.errors
    scopes = [b.scope for b in result.boundaries]
    assert any("gen_on.u_on" in s for s in scopes), scopes


@pytest.mark.skipif(FILELIST is None, reason="unified_verify corpus not available")
def test_unified_verify_md2d_deep_path_walk():
    """Multi-dim arrays: two branches cross-linked via probe_out/probe_in."""
    fl = parse_filelist(str(FILELIST), index_cwd=str(UNIFIED_VERIFY))
    deep_a = f"{TOP}.u_md2d.a.b.c[0][1].d.e.f[1].g[0][2]"
    deep_b = f"{TOP}.u_md2d.a2.b.c[1][0].d.e.f[0].g[1][1]"
    index, state, top = run_path_walk_index(
        fl,
        [deep_a, deep_b, f"{deep_a}.clk", f"{TOP}.clk"],
        top=TOP,
        no_cache=True,
    )
    assert deep_a in state.rows_by_path
    assert deep_b in state.rows_by_path
    assert state.rows_by_path[deep_a].inst_leaf == "g[0][2]"
    assert state.rows_by_path[deep_b].inst_leaf == "g[1][1]"
    request = ConnectivityRequest(
        checks=(
            ConnectivityCheck(f"{TOP}.clk", f"{deep_a}.clk", check_id="md2d_clk"),
            ConnectivityCheck(
                f"{deep_a}.probe_out",
                f"{deep_b}.probe_in",
                check_id="md2d_branch_link",
            ),
        ),
        top=TOP,
    )
    batch, _idx2, _st2 = run_path_walk_connect(request, fl, top=TOP, no_cache=True)
    by_id = {r.check_id: r for r in batch.results}
    assert by_id["md2d_clk"].connected is True
    assert by_id["md2d_branch_link"].connected is True