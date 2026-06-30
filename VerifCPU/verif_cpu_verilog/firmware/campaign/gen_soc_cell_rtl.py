#!/usr/bin/env python3
"""Generate rtl/verif_vcpu_soc_cell.v — VCPU + AMBA bridge cells for SoC integration."""

from __future__ import annotations

import sys
from pathlib import Path

from amba_bus_registry import BUS_TYPES, iter_implemented_buses
from verilog_paths import REPO_ROOT

OUT = Path(REPO_ROOT) / "rtl" / "verif_vcpu_soc_cell.v"

# Bridge instance port wiring: (cell_port, bridge_port)
CELL_SPECS: dict[str, dict] = {
    "apb2": {
        "clk": ("PCLK", "PCLK"),
        "rst": ("PRESETn", "PRESETn"),
        "master_out": [
            "PADDR", "PSEL", "PENABLE", "PWRITE", "PWDATA",
        ],
        "master_in": ["PRDATA"],
        "module": "verif_apb2_master",
    },
    "apb3": {
        "clk": ("PCLK", "PCLK"),
        "rst": ("PRESETn", "PRESETn"),
        "master_out": [
            "PADDR", "PSEL", "PENABLE", "PWRITE", "PWDATA", "PSTRB",
        ],
        "master_in": ["PRDATA", "PREADY", "PSLVERR"],
        "module": "verif_apb_master",
    },
    "apb4": {
        "clk": ("PCLK", "PCLK"),
        "rst": ("PRESETn", "PRESETn"),
        "master_out": [
            "PADDR", "PSEL", "PENABLE", "PWRITE", "PWDATA", "PSTRB", "PPROT",
        ],
        "master_in": ["PRDATA", "PREADY", "PSLVERR"],
        "module": "verif_apb4_master",
    },
    "apb5": {
        "clk": ("PCLK", "PCLK"),
        "rst": ("PRESETn", "PRESETn"),
        "master_out": [
            "PADDR", "PSEL", "PENABLE", "PWRITE", "PWDATA", "PSTRB", "PPROT", "PWAKEUP",
        ],
        "master_in": ["PRDATA", "PREADY", "PSLVERR"],
        "module": "verif_apb5_master",
    },
    "ahb_lite": {
        "clk": ("HCLK", "HCLK"),
        "rst": ("HRESETn", "HRESETn"),
        "master_out": ["HADDR", "HSIZE", "HTRANS", "HWRITE", "HWDATA"],
        "master_in": ["HRDATA", "HREADY", "HRESP"],
        "module": "verif_ahb_lite_master",
    },
    "ahb5_lite": {
        "clk": ("HCLK", "HCLK"),
        "rst": ("HRESETn", "HRESETn"),
        "master_out": [
            "HADDR", "HSIZE", "HTRANS", "HWRITE", "HWDATA", "HNONSEC", "HEXCL",
        ],
        "master_in": ["HRDATA", "HREADY", "HRESP", "HEXOK"],
        "module": "verif_ahb5_lite_master",
    },
    "ahb": {
        "clk": ("HCLK", "HCLK"),
        "rst": ("HRESETn", "HRESETn"),
        "master_out": [
            "HADDR", "HSIZE", "HTRANS", "HBURST", "HPROT", "HMASTLOCK",
            "HWRITE", "HWDATA", "HNONSEC", "HEXCL",
        ],
        "master_in": ["HRDATA", "HREADY", "HRESP", "HEXOK"],
        "module": "verif_ahb_master",
    },
    "axi4lite": {
        "clk": ("ACLK", "ACLK"),
        "rst": ("ARESETn", "ARESETn"),
        "master_out": [
            "ARVALID", "ARADDR", "ARSIZE", "RREADY",
            "AWVALID", "AWADDR", "AWSIZE", "WVALID", "WDATA", "WSTRB", "BREADY",
        ],
        "master_in": [
            "ARREADY", "RVALID", "RDATA", "RRESP",
            "AWREADY", "WREADY", "BVALID", "BRESP",
        ],
        "module": "verif_axi_lite_master",
    },
    "axi3full": {
        "clk": ("ACLK", "ACLK"),
        "rst": ("ARESETn", "ARESETn"),
        "axi_prot": 3,
        "master_out": [
            "ARID", "ARADDR", "ARLEN", "ARSIZE", "ARBURST", "ARVALID", "RREADY",
            "AWID", "AWADDR", "AWLEN", "AWSIZE", "AWBURST", "AWVALID",
            "WID", "WDATA", "WSTRB", "WLAST", "WVALID", "BREADY",
        ],
        "master_in": [
            "ARREADY", "RID", "RVALID", "RDATA", "RRESP", "RLAST",
            "AWREADY", "WREADY", "BID", "BVALID", "BRESP",
        ],
        "module": "verif_axi_full_master",
    },
    "axi4full": {
        "clk": ("ACLK", "ACLK"),
        "rst": ("ARESETn", "ARESETn"),
        "axi_prot": 4,
        "master_out": [
            "ARID", "ARADDR", "ARLEN", "ARSIZE", "ARBURST", "ARQOS", "ARREGION", "ARVALID", "RREADY",
            "AWID", "AWADDR", "AWLEN", "AWSIZE", "AWBURST", "AWQOS", "AWREGION", "AWATOP", "AWVALID",
            "WID", "WDATA", "WSTRB", "WLAST", "WVALID", "BREADY",
        ],
        "master_in": [
            "ARREADY", "RID", "RVALID", "RDATA", "RRESP", "RLAST",
            "AWREADY", "WREADY", "BID", "BVALID", "BRESP",
        ],
        "module": "verif_axi_full_master",
    },
    "axi5full": {
        "clk": ("ACLK", "ACLK"),
        "rst": ("ARESETn", "ARESETn"),
        "axi_prot": 5,
        "master_out": [
            "ARID", "ARADDR", "ARLEN", "ARSIZE", "ARBURST", "ARQOS", "ARREGION", "ARVALID", "RREADY",
            "AWID", "AWADDR", "AWLEN", "AWSIZE", "AWBURST", "AWQOS", "AWREGION", "AWATOP", "AWVALID",
            "WID", "WDATA", "WSTRB", "WLAST", "WVALID", "BREADY",
        ],
        "master_in": [
            "ARREADY", "RID", "RVALID", "RDATA", "RRESP", "RLAST",
            "AWREADY", "WREADY", "BID", "BVALID", "BRESP",
        ],
        "module": "verif_axi_full_master",
    },
}


def _port_dir(name: str, spec: dict) -> str:
    if name in spec["master_out"]:
        return "output"
    if name in spec["master_in"]:
        return "input"
    if name.startswith(("AR", "AW", "W", "B")) and name not in spec["master_in"]:
        return "output"
    if name in ("RREADY", "BREADY"):
        return "output"
    return "input"


def _port_decl(name: str, spec: dict) -> str:
    direction = _port_dir(name, spec)
    if name in ("RRESP", "BRESP", "HRESP"):
        return f"{direction} wire [1:0]  {name}"
    if name == "HTRANS":
        return f"{direction} wire [1:0]  {name}"
    if name in ("HSIZE", "ARSIZE", "AWSIZE", "HBURST", "ARBURST", "AWBURST"):
        return f"{direction} wire [2:0]  {name}"
    if name in ("ARLEN", "AWLEN"):
        return f"{direction} wire [7:0]  {name}"
    if name in ("ARID", "AWID", "WID", "RID", "BID"):
        return f"{direction} wire [3:0]  {name}"
    if name in ("PSTRB", "WSTRB"):
        return f"{direction} wire [3:0]  {name}"
    if name in ("PPROT",):
        return f"{direction} wire [2:0]  {name}"
    if name in ("ARQOS", "AWQOS"):
        return f"{direction} wire [3:0]  {name}"
    if name in ("ARREGION", "AWREGION"):
        return f"{direction} wire [3:0]  {name}"
    if name in ("AWATOP",):
        return f"{direction} wire [5:0]  {name}"
    if name in (
        "PADDR", "PWDATA", "PRDATA", "HADDR", "HWDATA", "HRDATA",
        "ARADDR", "AWADDR", "WDATA", "RDATA",
    ):
        return f"{direction} wire [31:0] {name}"
    return f"{direction} wire        {name}"


def emit_cell_module(key: str, spec: dict, bt_spec) -> list[str]:
    clk_p, _ = spec["clk"]
    rst_p, _ = spec["rst"]
    ports = [clk_p, rst_p]
    ports.extend(spec["master_out"])
    ports.extend(spec["master_in"])
    seen = set()
    ordered_ports = []
    for p in ports:
        if p not in seen:
            seen.add(p)
            ordered_ports.append(p)

    mod = spec["module"]
    lines = [
        f"// {bt_spec.label} — VCPU + bridge (connect VH: g_slv[cpu_id-1].u_bus.u_bridge)",
        f"module verif_vcpu_soc_cell_{key} #(",
        "  parameter integer CPU_ID = 1",
    ]
    if "axi_prot" in spec:
        lines.append(f"  ,parameter integer AXI_PROT = {spec['axi_prot']}")
    lines.extend([
        ") (",
        f"  input  wire {clk_p},",
        f"  input  wire {rst_p},",
    ])
    for p in ordered_ports:
        if p in (clk_p, rst_p):
            continue
        lines.append(f"  {_port_decl(p, spec)},")
    lines.extend([
        "  output wire        snoop_valid,",
        "  output wire        snoop_wr,",
        "  output wire [31:0] snoop_addr,",
        "  output wire [31:0] snoop_data",
        ");",
    ])

    bridge_params = ""
    if "axi_prot" in spec:
        bridge_params = "#(.AXI_PROT(AXI_PROT)) "

    lines.append(f"  {mod} {bridge_params}u_bridge (")
    lines.append(f"    .{clk_p}({clk_p}), .{rst_p}({rst_p}),")
    for p in ordered_ports:
        if p in (clk_p, rst_p):
            continue
        lines.append(f"    .{p}({p}),")
    lines.extend([
        "    .snoop_valid(snoop_valid),",
        "    .snoop_wr(snoop_wr),",
        "    .snoop_addr(snoop_addr),",
        "    .snoop_data(snoop_data)",
        "  );",
        "",
        "  verif_cpu_core #(",
        "    .CPU_ID(CPU_ID),",
        "    .USE_SHARED_BUS(0),",
        "    .USE_SHARED_POOL(0),",
        "    .USE_SOC_BUS(0),",
        "    .USE_MANIFEST_SOC_BUS(1)",
        "  ) u_cpu (",
        "    .final_pc(),",
        "    .total_steps(),",
        "    .sim_stop(),",
        "    .assert_pass(),",
        "    .assert_fail(),",
        "    .bus_txn_count(),",
        "    .unique_pcs(),",
        "    .recovery_count(),",
        "    .trace_depth_out(),",
        "    .instr_steps_traced()",
        "  );",
        "",
        "endmodule",
        "",
    ])
    return lines


def emit_dispatcher() -> list[str]:
    keys = [s.key for s in iter_implemented_buses() if s.key in CELL_SPECS]
    lines = [
        "// Dispatcher — pick cell module from manifest bus_type (see gen_tb_campaign.py)",
        "module verif_vcpu_soc_cell #(",
        "  parameter integer CPU_ID = 1,",
        "  parameter [8*16:1] BUS_TYPE = \"axi4lite\"",
        ")();",
        "  initial begin",
        "    $fatal(1, \"verif_vcpu_soc_cell: use verif_vcpu_soc_cell_<bus_type> or generated g_slv[].u_bus\");",
        "  end",
        "endmodule",
        "",
        f"// Implemented cell variants: {', '.join(keys)}",
        "",
    ]
    return lines


def main() -> int:
    lines = [
        "// Auto-generated by gen_soc_cell_rtl.py — do not edit",
        "`timescale 1ns/1ps",
        "`include \"verif_bus_defs.vh\"",
        "",
    ]
    lines.extend(emit_dispatcher())
    for key in sorted(CELL_SPECS.keys()):
        if key not in BUS_TYPES:
            continue
        bt = BUS_TYPES[key]
        if bt.rtl_status not in ("done", "smoke"):
            continue
        lines.extend(emit_cell_module(key, CELL_SPECS[key], bt))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    n = sum(1 for k in CELL_SPECS if k in BUS_TYPES and BUS_TYPES[k].rtl_status in ("done", "smoke"))
    print(f"[soc_cell] Wrote {OUT} ({n} bus cell module(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())