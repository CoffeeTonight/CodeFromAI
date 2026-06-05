"""Item 1: Tier E generate + instance array materialized paths."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GEN_FL = ROOT / "design" / "extras" / "gen_ifdef_generate" / "filelist.f"
ARR_DIR = ROOT / "design" / "extras" / "tier_e_array"


@pytest.fixture(scope="module")
def array_fixture(tmp_path_factory):
    d = tmp_path_factory.mktemp("tier_e_array")
    leaf = d / "leaf.v"
    top = d / "top.v"
    leaf.write_text(
        "module leaf(input clk, rst_n, output done);\nendmodule\n",
        encoding="utf-8",
    )
    top.write_text(
        """
module top(input clk, rst_n);
  leaf u_plain(.clk(clk), .rst_n(rst_n), .done());
  leaf u_arr[0:1](.clk(clk), .rst_n(rst_n), .done());
endmodule
""",
        encoding="utf-8",
    )
    return d


@pytest.mark.requires_engine
def test_tier_e_generate_paths():
    from hch.engine.pyslang_elab import elaborate_filelist

    result = elaborate_filelist(str(GEN_FL), top_modules=["top_soc"])
    assert result.succeeded
    paths = {e.full_path for e in result.instances}
    assert "top_soc.gen_blk.gen_loop[0].u_cell" in paths
    assert "top_soc.gen_blk.gen_loop[1].u_cell" in paths
    assert "top_soc.u_alt" in paths
    by_path = {e.full_path: e for e in result.instances}
    assert by_path["top_soc.gen_blk.gen_loop[0].u_cell"].inst_name == "u_cell"
    assert by_path["top_soc.gen_blk.gen_loop[0].u_cell"].depth == 3


@pytest.mark.requires_engine
def test_tier_e_instance_array_paths(array_fixture):
    from hch.engine.pyslang_elab import elaborate_instances

    d = array_fixture
    result = elaborate_instances(
        [str(d / "leaf.v"), str(d / "top.v")], top_modules=["top"]
    )
    assert result.succeeded
    paths = {e.full_path for e in result.instances}
    assert "top.u_arr[0]" in paths
    assert "top.u_arr[1]" in paths
    leaves = {e.inst_name for e in result.instances if "u_arr" in e.full_path}
    assert "u_arr[0]" in leaves
    assert "u_arr[1]" in leaves


@pytest.mark.requires_engine
def test_index_elab_meta(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "gen.hch.db"
    store = build_index_from_filelist(
        str(GEN_FL), str(db), top_module="top_soc", elaborate=True
    )
    assert int(store.get_meta("elab_succeeded", "0")) == 1
    n = store.count_instances()
    store.close()
    assert n >= 4