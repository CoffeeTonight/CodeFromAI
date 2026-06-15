// Customer chip_top reference — cells + CONNECT_SLV* + orchestrator + agent + bus R/W
// make chip-top-example

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"
`include "campaign_scale.vh"
`include "verif_soc_bus_connect.vh"

module chip_top_example;

  localparam MAX_GI = `CAMPAIGN_MAX_SLOTS;
  localparam HIER_N = 4;

  reg soc_clk = 0;
  reg soc_rstn = 0;
  always #5 soc_clk = ~soc_clk;

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;

  wire [MAX_GI-1:0]        g_slv_snoop_v;
  wire [MAX_GI-1:0]        g_slv_snoop_wr;
  wire [31:0] g_slv_snoop_addr [0:MAX_GI-1];
  wire [31:0] g_slv_snoop_data [0:MAX_GI-1];

  wire [31:0] sl_slot_count [0:MAX_GI-1];
  wire [31:0] sl_pass       [0:MAX_GI-1];
  wire [31:0] sl_fail       [0:MAX_GI-1];
  wire [31:0] sl_txns       [0:MAX_GI-1];

  wire [31:0] S01_APB_PADDR, S01_APB_PWDATA, S01_APB_PRDATA;
  wire        S01_APB_PSEL, S01_APB_PENABLE, S01_APB_PWRITE;
  wire [3:0]  S01_APB_PSTRB;
  wire        S01_APB_PREADY, S01_APB_PSLVERR;

  wire [31:0] M02_AHB_HADDR, M02_AHB_HWDATA, M02_AHB_HRDATA;
  wire [2:0]  M02_AHB_HSIZE;
  wire [1:0]  M02_AHB_HTRANS, M02_AHB_HRESP;
  wire        M02_AHB_HWRITE, M02_AHB_HREADY, M02_AHB_HREADYOUT;

  wire        S03_AXI_arvalid, S03_AXI_arready, S03_AXI_rvalid, S03_AXI_rready;
  wire        S03_AXI_awvalid, S03_AXI_awready, S03_AXI_wvalid, S03_AXI_wready;
  wire        S03_AXI_bvalid, S03_AXI_bready;
  wire [31:0] S03_AXI_araddr, S03_AXI_awaddr, S03_AXI_wdata, S03_AXI_rdata;
  wire [2:0]  S03_AXI_arsize, S03_AXI_awsize;
  wire [3:0]  S03_AXI_wstrb;
  wire [1:0]  S03_AXI_rresp, S03_AXI_bresp;
  wire [3:0]  S03_AXI_rid, S03_AXI_bid;
  wire        S03_AXI_rlast;

  wire        S37_AXI_arvalid, S37_AXI_arready, S37_AXI_rvalid, S37_AXI_rready;
  wire        S37_AXI_awvalid, S37_AXI_awready, S37_AXI_wvalid, S37_AXI_wready;
  wire        S37_AXI_bvalid, S37_AXI_bready;
  wire [31:0] S37_AXI_araddr, S37_AXI_awaddr, S37_AXI_wdata, S37_AXI_rdata;
  wire [2:0]  S37_AXI_arsize, S37_AXI_awsize;
  wire [3:0]  S37_AXI_wstrb;
  wire [1:0]  S37_AXI_rresp, S37_AXI_bresp;
  wire [3:0]  S37_AXI_rid, S37_AXI_bid;
  wire        S37_AXI_rlast;

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count()
  );

  verif_apb_slave_simple #(.BASE(32'h4000_0000)) u_periph_sfr (
    .PCLK(soc_clk), .PRESETn(soc_rstn),
    .PADDR(S01_APB_PADDR), .PSEL(S01_APB_PSEL), .PENABLE(S01_APB_PENABLE),
    .PWRITE(S01_APB_PWRITE), .PWDATA(S01_APB_PWDATA), .PSTRB(S01_APB_PSTRB),
    .PRDATA(S01_APB_PRDATA), .PREADY(S01_APB_PREADY), .PSLVERR(S01_APB_PSLVERR)
  );

  verif_ahb_lite_slave_simple #(.BASE(32'h8000_0000)) u_periph_sram (
    .HCLK(soc_clk), .HRESETn(soc_rstn),
    .HADDR(M02_AHB_HADDR), .HSIZE(M02_AHB_HSIZE), .HTRANS(M02_AHB_HTRANS),
    .HWRITE(M02_AHB_HWRITE), .HWDATA(M02_AHB_HWDATA), .HREADY(M02_AHB_HREADY),
    .HRDATA(M02_AHB_HRDATA), .HREADYOUT(M02_AHB_HREADYOUT), .HRESP(M02_AHB_HRESP)
  );

  assign S03_AXI_rid = 4'd0;
  assign S03_AXI_bid = 4'd0;
  assign S03_AXI_rlast = 1'b1;
  verif_axi_full_slave_simple #(.BASE(32'hC000_0000)) u_periph_uart (
    .ACLK(soc_clk), .ARESETn(soc_rstn),
    .ARID(4'd0), .ARADDR(S03_AXI_araddr), .ARLEN(8'd0), .ARSIZE(S03_AXI_arsize),
    .ARBURST(2'b01), .ARVALID(S03_AXI_arvalid), .ARREADY(S03_AXI_arready),
    .RID(S03_AXI_rid), .RDATA(S03_AXI_rdata), .RRESP(S03_AXI_rresp),
    .RLAST(S03_AXI_rlast), .RVALID(S03_AXI_rvalid), .RREADY(S03_AXI_rready),
    .AWID(4'd0), .AWADDR(S03_AXI_awaddr), .AWLEN(8'd0), .AWSIZE(S03_AXI_awsize),
    .AWBURST(2'b01), .AWVALID(S03_AXI_awvalid), .AWREADY(S03_AXI_awready),
    .WID(4'd0), .WDATA(S03_AXI_wdata), .WSTRB(S03_AXI_wstrb), .WLAST(1'b1),
    .WVALID(S03_AXI_wvalid), .WREADY(S03_AXI_wready),
    .BID(S03_AXI_bid), .BRESP(S03_AXI_bresp), .BVALID(S03_AXI_bvalid), .BREADY(S03_AXI_bready)
  );

  assign S37_AXI_rid = 4'd0;
  assign S37_AXI_bid = 4'd0;
  assign S37_AXI_rlast = 1'b1;
  verif_axi_full_slave_simple #(.BASE(32'h4A00_0000)) u_periph_dma (
    .ACLK(soc_clk), .ARESETn(soc_rstn),
    .ARID(4'd0), .ARADDR(S37_AXI_araddr), .ARLEN(8'd0), .ARSIZE(S37_AXI_arsize),
    .ARBURST(2'b01), .ARVALID(S37_AXI_arvalid), .ARREADY(S37_AXI_arready),
    .RID(S37_AXI_rid), .RDATA(S37_AXI_rdata), .RRESP(S37_AXI_rresp),
    .RLAST(S37_AXI_rlast), .RVALID(S37_AXI_rvalid), .RREADY(S37_AXI_rready),
    .AWID(4'd0), .AWADDR(S37_AXI_awaddr), .AWLEN(8'd0), .AWSIZE(S37_AXI_awsize),
    .AWBURST(2'b01), .AWVALID(S37_AXI_awvalid), .AWREADY(S37_AXI_awready),
    .WID(4'd0), .WDATA(S37_AXI_wdata), .WSTRB(S37_AXI_wstrb), .WLAST(1'b1),
    .WVALID(S37_AXI_wvalid), .WREADY(S37_AXI_wready),
    .BID(S37_AXI_bid), .BRESP(S37_AXI_bresp), .BVALID(S37_AXI_bvalid), .BREADY(S37_AXI_bready)
  );

  verif_cpu_unified_pool #(.MEM_WORDS(32'h1000)) u_pool ();

  `include "chip_top_example_gen.vh"
  `include "chip_top_decode.vh"

  integer pass, fail;
  reg [31:0] wdata, rdata;
  reg [1:0]  wresp, rresp, rport;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  task chip_bus_wr_rd;
    input [8*64:1] label;
    input [31:0]   addr;
    input [31:0]   pattern;
    begin
      chip_decode_write(addr, pattern, 3'd4, wresp, rport);
      check({label, " write OK"}, wresp == 2'd0);
      chip_decode_read(addr, 3'd4, rdata, rresp, rport);
      check({label, " read OK"}, rresp == 2'd0);
      check({label, " data match"}, rdata == pattern);
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    soc_rstn = 1'b0;
    repeat (4) @(posedge soc_clk);
    soc_rstn = 1'b1;
    repeat (2) @(posedge soc_clk);

    $display("========================================================================");
    $display("chip_top_example: orchestrator + agent + bridge bus R/W (%0d cells)", HIER_N);
    $display("========================================================================");

    u_orch.phase_release(`PHASE_INIT, 32'h0);

    chip_bus_wr_rd("SFR APB",  32'h4000_0000, 32'h0000_CAFE);
    chip_bus_wr_rd("SRAM AHB", 32'h8000_0000, 32'h1234_5678);
    chip_bus_wr_rd("UART AXI", 32'hC000_0000, 32'h0000_00A5);
    chip_bus_wr_rd("DMA AXI",  32'h4A00_0000, 32'hDEAD_BEEF);

    u_ag_1.run_phase_a();
    u_ag_2.run_phase_a();
    u_ag_3.run_phase_a();
    u_ag_37.run_phase_a();

    check("Agent SFR saw bridge traffic",  sl_txns[0] > 0);
    check("Agent SRAM saw bridge traffic", sl_txns[1] > 0);
    check("Agent UART saw bridge traffic", sl_txns[2] > 0);
    check("Agent DMA saw bridge traffic",  sl_txns[36] > 0);

    $display("");
    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "chip_top_example FAILED");
    $display("chip_top_example: PASS");
    $finish;
  end

endmodule