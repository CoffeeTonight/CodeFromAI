// =============================================================================
// soc_cpu_bus_paste — copy-paste VCPU integration (1 slave on 1 SoC bus port)
// Guide: integration_paste.md  |  Run: make soc-paste
// =============================================================================

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"
`include "verif_amba_connect_macros.vh"
`include "verif_sim_watchdog.vh"

module soc_cpu_bus_paste;

  localparam integer TB_EXPECTED_PASS = 4;

  `VERIF_SIM_WATCHDOG_NS

  reg soc_clk = 0;
  reg soc_rstn = 0;
  always #5 soc_clk = ~soc_clk;

  wire        S01_AXI_arvalid, S01_AXI_arready, S01_AXI_rvalid, S01_AXI_rready;
  wire        S01_AXI_awvalid, S01_AXI_awready, S01_AXI_wvalid, S01_AXI_wready;
  wire        S01_AXI_bvalid, S01_AXI_bready;
  wire [31:0] S01_AXI_araddr, S01_AXI_awaddr, S01_AXI_wdata, S01_AXI_rdata;
  wire [2:0]  S01_AXI_arsize, S01_AXI_awsize;
  wire [3:0]  S01_AXI_wstrb;
  wire [1:0]  S01_AXI_rresp, S01_AXI_bresp;

  localparam [31:0] SOC_PERIPH_BASE = 32'h4000_0000;

  wire [3:0] u_stub_rid, u_stub_bid;
  wire       u_stub_rlast;

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count()
  );

  wire        snoop_valid, snoop_wr;
  wire [31:0] snoop_addr, snoop_data;
  wire [31:0] sl_txns;

  verif_agent_slave #(
    .CPU_ID(1),
    .CPU_NAME("PASTE  "),
    .TAP_PORT(0)
  ) u_ag (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .txn_valid(snoop_valid),
    .txn_is_write(snoop_wr),
    .txn_addr(snoop_addr),
    .txn_data(snoop_data),
    .icode_ptr(32'h0),
    .icode_kind(3'd0),
    .slot_count(),
    .verify_pass(),
    .verify_fail(),
    .txn_recorded(sl_txns)
  );

  verif_axi_full_slave_simple #(
    .BASE(SOC_PERIPH_BASE),
    .INIT_WORD0(32'h0000_00C0)
  ) u_company_periph_stub (
    .ACLK(soc_clk),
    .ARESETn(soc_rstn),
    .ARID(4'd0),
    .ARADDR(S01_AXI_araddr),
    .ARLEN(8'd0),
    .ARSIZE(S01_AXI_arsize),
    .ARBURST(2'b01),
    .ARLOCK(1'b0),
    .ARVALID(S01_AXI_arvalid),
    .ARREADY(S01_AXI_arready),
    .RID(u_stub_rid),
    .RDATA(S01_AXI_rdata),
    .RRESP(S01_AXI_rresp),
    .RLAST(u_stub_rlast),
    .RVALID(S01_AXI_rvalid),
    .RREADY(S01_AXI_rready),
    .AWID(4'd0),
    .AWADDR(S01_AXI_awaddr),
    .AWLEN(8'd0),
    .AWSIZE(S01_AXI_awsize),
    .AWBURST(2'b01),
    .AWLOCK(1'b0),
    .AWVALID(S01_AXI_awvalid),
    .AWREADY(S01_AXI_awready),
    .WID(4'd0),
    .WDATA(S01_AXI_wdata),
    .WSTRB(S01_AXI_wstrb),
    .WLAST(1'b1),
    .WVALID(S01_AXI_wvalid),
    .WREADY(S01_AXI_wready),
    .BID(u_stub_bid),
    .BRESP(S01_AXI_bresp),
    .BVALID(S01_AXI_bvalid),
    .BREADY(S01_AXI_bready)
  );

  `include "soc_cpu_bus_paste_fabric.vh"
  `include "soc_cpu_bus_paste_tasks.vh"

endmodule