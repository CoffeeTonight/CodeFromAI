"""path_refine instance parsing parity with inst_scan."""

from __future__ import annotations

from pathlib import Path

from scan_inst.index import DesignIndex
from scan_inst.path_refine import _body_prefix_before_instance, refine_param_ctx_for_path
from scan_inst.preprocess import preprocess_file


def test_body_prefix_matches_array_inst_name(tmp_path: Path):
    body = """
      localparam W_EARLY = 4;
      child #( .W(W_EARLY) ) u_arr[0] ();
      localparam W_LATE = 32;
    """
    prefix = _body_prefix_before_instance(body, "u_arr[0]")
    assert "W_EARLY" in prefix
    assert "W_LATE" not in prefix


def test_body_prefix_matches_hierarchical_inst_leaf(tmp_path: Path):
    body = """
      localparam W_EARLY = 4;
      child genblk.u_target ();
      localparam W_LATE = 32;
    """
    prefix = _body_prefix_before_instance(body, "u_target")
    assert "W_EARLY" in prefix
    assert "W_LATE" not in prefix


def test_refine_param_ctx_for_array_inst(tmp_path: Path):
    rtl = tmp_path / "arr.v"
    rtl.write_text(
        """
        module top;
          localparam W_EARLY = 8;
          child #( .W(W_EARLY) ) u_arr[0] ();
          localparam W_LATE = 64;
        endmodule
        module child #(parameter int W = 1) (
            input logic [W-1:0] data
        );
        endmodule
        """,
        encoding="utf-8",
    )
    text = preprocess_file(rtl, [], {})
    index = DesignIndex.build({str(rtl): text})
    result = refine_param_ctx_for_path(index, "top", "top.u_arr[0]")
    assert result.ok
    assert result.param_ctx.get("W") == "8"