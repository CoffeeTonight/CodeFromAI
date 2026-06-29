#!/usr/bin/env python3
"""Generate paste-style SoC integration example from soc_integration_ports.yaml.

Direct inst-level wiring (no CONNECT macros): VCPU cell + agent + stub per slave row.
Optional YAML — make skips when file absent; creates example on next make when ready.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gen_tb_campaign import (  # noqa: E402
    _CHIP_BUS_TEST_PATTERNS,
    cell_module_for,
    emit_chip_agents,
    emit_chip_top_snoop_wires,
    emit_scale_soc_port_wires,
    emit_soc_axi_id_assigns,
    emit_soc_stub_periph,
    load_soc_hierarchy_yaml,
    normalize_bus_type,
)
from verilog_paths import INCLUDE_DIR

ROOT = Path(__file__).resolve().parent
DEFAULT_YAML = ROOT / "soc_integration_ports.yaml"
OUT_GEN_VH = Path(INCLUDE_DIR) / "soc_integration_example_gen.vh"
OUT_TB = Path(INCLUDE_DIR).parent / "tb" / "soc_integration_example.v"


def _axi_sig(pref: str, sig: str) -> str:
    return f"{pref}_{sig.lower()}"


def emit_direct_cell_instance(s: dict) -> list[str]:
    """VCPU soc cell with SoC port prefix wired directly (paste style)."""
    gi = s["cpu_id"] - 1
    cid = s["cpu_id"]
    pref = str(s["bus_port"]).strip()
    bt = normalize_bus_type(s["bus_type"])
    mod = cell_module_for(bt)
    indent = "      "
    lines = [f"    begin : g_slv{gi}", f"{indent}{mod} #(.CPU_ID({cid})) u_bus ("]

    if bt.startswith("apb"):
        lines.extend([
            f"{indent}.PCLK(soc_clk), .PRESETn(soc_rstn),",
            f"{indent}.PADDR({pref}_PADDR), .PSEL({pref}_PSEL), .PENABLE({pref}_PENABLE),",
            f"{indent}.PWRITE({pref}_PWRITE), .PWDATA({pref}_PWDATA), .PSTRB({pref}_PSTRB),",
        ])
        if bt in ("apb4", "apb5"):
            lines.append(f"{indent}.PPROT({pref}_PPROT),")
        if bt == "apb5":
            lines.append(f"{indent}.PWAKEUP({pref}_PWAKEUP),")
        lines.append(
            f"{indent}.PRDATA({pref}_PRDATA), .PREADY({pref}_PREADY), .PSLVERR({pref}_PSLVERR),"
        )
    elif bt.startswith("ahb"):
        hexok = f"\n{indent}.HEXOK(1'b1)," if bt in ("ahb5_lite", "ahb") else ""
        if bt == "ahb_lite":
            bus_ports = (
                f"{indent}.HADDR({pref}_HADDR), .HSIZE({pref}_HSIZE), .HTRANS({pref}_HTRANS),"
                f"\n{indent}.HWRITE({pref}_HWRITE), .HWDATA({pref}_HWDATA), .HREADY({pref}_HREADY),"
                f"\n{indent}.HRDATA({pref}_HRDATA), .HREADYOUT({pref}_HREADYOUT), .HRESP({pref}_HRESP),"
            )
        elif bt == "ahb5_lite":
            bus_ports = (
                f"{indent}.HADDR({pref}_HADDR), .HSIZE({pref}_HSIZE), .HTRANS({pref}_HTRANS),"
                f"\n{indent}.HWRITE({pref}_HWRITE), .HWDATA({pref}_HWDATA), .HREADY({pref}_HREADY),"
                f"\n{indent}.HNONSEC({pref}_HNONSEC), .HEXCL({pref}_HEXCL),"
                f"\n{indent}.HRDATA({pref}_HRDATA), .HREADYOUT({pref}_HREADYOUT),"
                f" .HRESP({pref}_HRESP), .HEXOK({pref}_HEXOK),"
            )
        else:
            bus_ports = (
                f"{indent}.HADDR({pref}_HADDR), .HSIZE({pref}_HSIZE), .HTRANS({pref}_HTRANS),"
                f" .HBURST({pref}_HBURST), .HPROT({pref}_HPROT), .HMASTLOCK({pref}_HMASTLOCK),"
                f"\n{indent}.HWRITE({pref}_HWRITE), .HWDATA({pref}_HWDATA), .HREADY({pref}_HREADY),"
                f"\n{indent}.HNONSEC({pref}_HNONSEC), .HEXCL({pref}_HEXCL),"
                f"\n{indent}.HRDATA({pref}_HRDATA), .HREADYOUT({pref}_HREADYOUT),"
                f" .HRESP({pref}_HRESP), .HEXOK({pref}_HEXOK),"
            )
        lines.append(f"{indent}.HCLK(soc_clk), .HRESETn(soc_rstn),{hexok}")
        lines.append(bus_ports)
    elif bt == "axi4lite":
        lines.extend([
            f"{indent}.ACLK(soc_clk), .ARESETn(soc_rstn),",
            f"{indent}.ARVALID({_axi_sig(pref, 'ARVALID')}), .ARADDR({_axi_sig(pref, 'ARADDR')}),",
            f" .ARSIZE({_axi_sig(pref, 'ARSIZE')}), .RREADY({_axi_sig(pref, 'RREADY')}),",
            f"{indent}.AWVALID({_axi_sig(pref, 'AWVALID')}), .AWADDR({_axi_sig(pref, 'AWADDR')}),",
            f" .AWSIZE({_axi_sig(pref, 'AWSIZE')}), .WVALID({_axi_sig(pref, 'WVALID')}),",
            f" .WDATA({_axi_sig(pref, 'WDATA')}), .WSTRB({_axi_sig(pref, 'WSTRB')}),",
            f" .BREADY({_axi_sig(pref, 'BREADY')}),",
            f"{indent}.ARREADY({_axi_sig(pref, 'ARREADY')}), .RVALID({_axi_sig(pref, 'RVALID')}),",
            f" .RDATA({_axi_sig(pref, 'RDATA')}), .RRESP({_axi_sig(pref, 'RRESP')}),",
            f"{indent}.AWREADY({_axi_sig(pref, 'AWREADY')}), .WREADY({_axi_sig(pref, 'WREADY')}),",
            f" .BVALID({_axi_sig(pref, 'BVALID')}), .BRESP({_axi_sig(pref, 'BRESP')}),",
        ])
    else:
        raise ValueError(
            f"slave {s['name']}: bus_type {bt!r} — integration example supports "
            "apb2/3/4/5, ahb_lite/ahb5_lite/ahb, axi4lite (add more in generator if needed)"
        )

    lines.extend([
        f"{indent}.snoop_valid(g_slv_snoop_v[{gi}]), .snoop_wr(g_slv_snoop_wr[{gi}]),",
        f"{indent}.snoop_addr(g_slv_snoop_addr[{gi}]), .snoop_data(g_slv_snoop_data[{gi}])",
        f"{indent});",
        "    end",
        "",
    ])
    return lines


def emit_direct_fabric(slaves: list[dict]) -> list[str]:
    lines = [
        "  // Auto-generated VCPU cells — direct SoC port wiring (paste style)",
        "  generate",
    ]
    for s in slaves:
        lines.extend(emit_direct_cell_instance(s))
    lines.extend(["  endgenerate", ""])
    return lines


def emit_smoke_initial(slaves: list[dict]) -> list[str]:
    lines = [
        "  integer pass, fail;",
        "  reg [31:0] wdata, rdata;",
        "  reg [1:0]  resp;",
        "",
        "  task check;",
        "    input [8*96:1] name;",
        "    input ok;",
        "    begin",
        "      if (ok) begin pass = pass + 1; $display(\"  [PASS] %0s\", name); end",
        "      else begin fail = fail + 1; $display(\"  [FAIL] %0s\", name); end",
        "    end",
        "  endtask",
        "",
        "  initial begin",
        "    pass = 0;",
        "    fail = 0;",
        "    soc_rstn = 1'b0;",
        "    repeat (4) @(posedge soc_clk);",
        "    soc_rstn = 1'b1;",
        "    repeat (2) @(posedge soc_clk);",
        "",
        "    $display(\"========================================================================\");",
        f'    $display("soc_integration_example: paste-style inst integration (%0d ports)",'
        f" {len(slaves)});",
        "    $display(\"========================================================================\");",
        "",
    ]
    for i, s in enumerate(slaves):
        gi = s["cpu_id"] - 1
        base = int(s.get("addr_base") or 0)
        pat = _CHIP_BUS_TEST_PATTERNS[i % len(_CHIP_BUS_TEST_PATTERNS)]
        bt = normalize_bus_type(s["bus_type"]).upper()
        label = f'{s["name"]} {bt}'
        lines.extend([
            f"    wdata = 32'h{pat:08X};",
            f"    g_slv{gi}.u_bus.u_bridge.bus_write(32'h{base:08X}, wdata, 3'd4, resp);",
            f'    check("{label} write OK", resp == 2\'d0);',
            f"    g_slv{gi}.u_bus.u_bridge.bus_read(32'h{base:08X}, 3'd4, rdata, resp);",
            f'    check("{label} read OK", resp == 2\'d0);',
            f'    check("{label} data match", rdata == wdata);',
            f'    check("Agent {s["name"]} snoop", sl_txns[{gi}] > 0);',
            "",
        ])
    lines.extend([
        "    $display(\"Checklist: %0d passed / %0d failed\", pass, fail);",
        "    if (fail != 0) $fatal(1, \"soc_integration_example FAILED\");",
        "    $display(\"soc_integration_example: PASS\");",
        "    $finish;",
        "  end",
        "",
    ])
    return lines


def generate(slaves: list[dict], soc_name: str) -> str:
    wired = [s for s in slaves if str(s.get("bus_port") or "").strip()]
    if not wired:
        raise ValueError("soc_integration_ports.yaml: no slaves with bus_port")

    max_cpu = max(s["cpu_id"] for s in wired)
    out: list[str] = [
        "// Auto-generated by gen_soc_integration_example.py — do not edit",
        f"// SSOT: soc_integration_ports.yaml (soc_name={soc_name})",
        "// Direct inst wiring — copy g_slvN blocks into your chip_top",
        "",
        f"  localparam INTEGRATION_N_PORTS = {len(wired)};",
        "",
    ]
    out.extend(emit_chip_top_snoop_wires(max_cpu))
    out.extend(emit_scale_soc_port_wires(wired))
    out.extend(emit_soc_axi_id_assigns(wired))
    out.extend(emit_soc_stub_periph(wired))
    out.extend(emit_direct_fabric(wired))
    out.extend(emit_chip_agents(wired))
    out.extend(emit_smoke_initial(wired))
    return "\n".join(out)


def write_tb_shell() -> None:
    content = """\
// Auto-generated shell — SSOT body in include/soc_integration_example_gen.vh
// YAML: firmware/campaign/soc_integration_ports.yaml  |  Run: make soc-integration

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"

module soc_integration_example;

  reg soc_clk = 0;
  reg soc_rstn = 0;
  always #5 soc_clk = ~soc_clk;

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count()
  );

  `include "soc_integration_example_gen.vh"

endmodule
"""
    OUT_TB.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yaml",
        default=str(DEFAULT_YAML),
        help="Port list YAML (default: soc_integration_ports.yaml)",
    )
    args = parser.parse_args()
    yaml_path = Path(args.yaml)
    if not yaml_path.is_file():
        print(
            f"[integration] ERROR: {yaml_path.name} not found — run make discover",
            file=sys.stderr,
        )
        return 1

    try:
        import yaml
    except ImportError:
        print("[integration] ERROR: PyYAML required", file=sys.stderr)
        return 1

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    slaves = load_soc_hierarchy_yaml(str(yaml_path))
    if not slaves:
        print(f"[integration] ERROR: no slaves[] in {yaml_path}", file=sys.stderr)
        return 1

    soc_name = str(raw.get("soc_name") or "integration_soc")
    body = generate(slaves, soc_name)
    OUT_GEN_VH.parent.mkdir(parents=True, exist_ok=True)
    OUT_GEN_VH.write_text(body, encoding="utf-8")
    write_tb_shell()
    names = ", ".join(f"{s['name']}@{s['bus_port']}" for s in slaves)
    print(f"[integration] Wrote {OUT_GEN_VH.name} + tb/soc_integration_example.v ({len(slaves)} ports: {names})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())