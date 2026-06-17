"""Wire/signal endpoints (not only module ports)."""

from __future__ import annotations

from pathlib import Path

from scan_inst.connectivity import check_connectivity
from scan_inst.connect_endpoints import parse_connect_endpoint, resolve_endpoint
from scan_inst.elab import elaborate
from scan_inst.index import DesignIndex
from scan_inst.path_walk import run_path_walk_connect
from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest
from scan_inst.filelist import parse_filelist


def _index_and_rows(verilog: str, tmp_path: Path, top: str = "top"):
    rtl = tmp_path / "d.v"
    rtl.write_text(verilog, encoding="utf-8")
    index = DesignIndex.build({str(rtl): verilog})
    _, rows = elaborate(index, top)
    return index, rows


def test_parse_connect_endpoint_accepts_internal_wire(tmp_path: Path):
    v = """
    module top(input logic clk);
      wire bridge;
      assign bridge = clk;
      child u0 (.clk(bridge));
    endmodule
    module child(input logic clk); endmodule
    """
    index, rows = _index_and_rows(v, tmp_path)
    lookup = {r.full_path: r for r in rows}
    hier, tail = parse_connect_endpoint("top.bridge", lookup, index=index, top="top")
    assert hier == "top"
    assert tail == "bridge"


def test_resolve_wire_endpoint(tmp_path: Path):
    v = """
    module top(input logic clk);
      wire bridge;
      assign bridge = clk;
    endmodule
    """
    index, rows = _index_and_rows(v, tmp_path)
    ep, errors = resolve_endpoint("top.bridge", rows, index, top="top")
    assert not errors
    assert ep.port_found
    assert ep.inst_path == "top"
    assert ep.port_name == "bridge"


def test_internal_wire_connected_only_via_instance_port(tmp_path: Path):
    """``wire c`` with no assign — only ``.p(c)`` — is a valid signal endpoint."""
    v = """
    module top(input logic clk);
      wire c;
      child u0 (.out(c));
    endmodule
    module child(output logic out);
      assign out = 1'b0;
    endmodule
    """
    index, rows = _index_and_rows(v, tmp_path)
    ep, errors = resolve_endpoint("top.c", rows, index, top="top")
    assert not errors
    assert ep.port_found
    r = check_connectivity(
        "top.u0.out",
        "top.c",
        rows=rows,
        index=index,
        top="top",
    )
    assert r.connected


def test_connectivity_port_to_internal_wire(tmp_path: Path):
    v = """
    module top(input logic clk);
      wire bridge;
      assign bridge = clk;
      child u0 (.clk(bridge));
    endmodule
    module child(input logic clk); endmodule
    """
    index, rows = _index_and_rows(v, tmp_path)
    r = check_connectivity("top.clk", "top.bridge", rows=rows, index=index, top="top")
    assert r.connected


def test_path_walk_miss_hints_module_type_not_inst_name(tmp_path: Path):
    (tmp_path / "top.v").write_text(
        """
        module SOC_TOP;
          CPUSYSTEM_TOP u_cpusystem_top (.clk(clk));
        endmodule
        """,
        encoding="utf-8",
    )
    (tmp_path / "cpu.v").write_text("module CPUSYSTEM_TOP; endmodule\n", encoding="utf-8")
    fl = tmp_path / "design.f"
    fl.write_text(
        "\n".join(str((tmp_path / n).resolve()) for n in ("top.v", "cpu.v")) + "\n",
        encoding="utf-8",
    )
    flr = parse_filelist(str(fl), index_cwd=str(tmp_path))
    import io

    buf = io.StringIO()
    req = ConnectivityRequest(
        checks=(ConnectivityCheck("SOC_TOP.CPUSYSTEM_TOP", "SOC_TOP.CPUSYSTEM_TOP"),),
        top="SOC_TOP",
    )
    run_path_walk_connect(req, flr, top="SOC_TOP", no_cache=True, trace_stream=buf)
    text = buf.getvalue()
    assert "module type" in text
    assert "u_cpusystem_top" in text