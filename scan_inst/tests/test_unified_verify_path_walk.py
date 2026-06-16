"""Path-walk integration on hc_hierarchy unified_verify corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist
from scan_inst.path_walk import build_path_walk_state_from_specs, create_path_walk_index, run_path_walk_connect

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