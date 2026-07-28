// Mid-transfer reset: OS wait must fail-fast with SOFT (no hang / WAIT_TICK fatal)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"
`include "verif_sim_watchdog.vh"

module tb_amba_mid_reset;

  localparam integer TB_EXPECTED_PASS = 4;

  `VERIF_SIM_WATCHDOG_NS

  reg clk = 0;
  reg rstn = 0;
  always #5 clk = ~clk;

  wire [31:0] axi_rdata;
  wire [3:0]  axi_rid, axi_bid;
  wire        axi_arready, axi_rvalid, axi_awready, axi_wready, axi_bvalid, axi_rlast;
  wire [1:0]  axi_rresp, axi_bresp;

  verif_axi_full_master #(.AXI_PROT(4), .ID_BASE(0), .MAX_OUTSTANDING(4)) u_axi (
    .ACLK(clk), .ARESETn(rstn),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARLOCK(), .ARVALID(),
    .ARREADY(axi_arready),
    .RID(axi_rid), .RDATA(axi_rdata), .RRESP(axi_rresp), .RLAST(axi_rlast),
    .RVALID(axi_rvalid), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWLOCK(), .AWVALID(),
    .AWREADY(axi_awready),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .WREADY(axi_wready),
    .BID(axi_bid), .BRESP(axi_bresp), .BVALID(axi_bvalid), .BREADY(),
    .AWQOS(), .AWREGION(), .AWATOP(), .ARQOS(), .ARREGION(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_axi_full_slave_simple #(
    .BASE(32'hA000_0000),
    .SIZE(32'h1000),
    .R_LATENCY(32),
    .B_LATENCY(4),
    .INIT_WORD0(32'h1111_1111)
  ) u_axi_s (
    .ACLK(clk), .ARESETn(rstn),
    .ARID(u_axi.ARID), .ARADDR(u_axi.ARADDR), .ARLEN(u_axi.ARLEN), .ARSIZE(u_axi.ARSIZE),
    .ARBURST(u_axi.ARBURST), .ARLOCK(u_axi.ARLOCK), .ARVALID(u_axi.ARVALID), .ARREADY(axi_arready),
    .RID(axi_rid), .RDATA(axi_rdata), .RRESP(axi_rresp), .RLAST(axi_rlast),
    .RVALID(axi_rvalid), .RREADY(u_axi.RREADY),
    .AWID(u_axi.AWID), .AWADDR(u_axi.AWADDR), .AWLEN(u_axi.AWLEN), .AWSIZE(u_axi.AWSIZE),
    .AWBURST(u_axi.AWBURST), .AWLOCK(u_axi.AWLOCK), .AWVALID(u_axi.AWVALID), .AWREADY(axi_awready),
    .WID(u_axi.WID), .WDATA(u_axi.WDATA), .WSTRB(u_axi.WSTRB), .WLAST(u_axi.WLAST),
    .WVALID(u_axi.WVALID), .WREADY(axi_wready),
    .BID(axi_bid), .BRESP(axi_bresp), .BVALID(axi_bvalid), .BREADY(u_axi.BREADY)
  );

  integer pass, fail;
  integer h, h2;
  reg ok, ok2;
  reg [31:0] rd;
  reg [1:0]  resp;

  task check;
    input [255:0] name;
    input         cond;
    begin
      if (cond) begin
        pass = pass + 1;
        $display("  [PASS] %0s", name);
      end else begin
        fail = fail + 1;
        $display("  [FAIL] %0s", name);
      end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    $dumpfile("sim_build/tb_amba_mid_reset.vcd");
    $dumpvars(0, tb_amba_mid_reset);
    repeat (4) @(posedge clk);
    rstn = 1'b1;
    repeat (2) @(posedge clk);
    $display("tb_amba_mid_reset: OS wait abort on mid-transfer reset");

    // Read: issue into latency slave, pulse reset, wait must SOFT-fail
    u_axi.bus_read_issue(32'hA000_0000, 3'd4, h, ok);
    check("read issue ok", ok && h >= 0);
    @(posedge clk);
    rstn = 1'b0;
    repeat (2) @(posedge clk);
    rstn = 1'b1;
    repeat (2) @(posedge clk);
    u_axi.bus_read_wait(h, rd, resp);
    check("read wait SOFT after reset",
          resp == `VERIF_BUS_RESP_SOFT && rd == 32'hDEADDEAD);

    // Write path: same contract
    u_axi.bus_write_issue(32'hA000_0010, 32'hCAFE_0001, 3'd4, h2, ok2);
    check("write issue ok", ok2 && h2 >= 0);
    @(posedge clk);
    rstn = 1'b0;
    repeat (2) @(posedge clk);
    rstn = 1'b1;
    repeat (2) @(posedge clk);
    u_axi.bus_write_wait(h2, resp);
    check("write wait SOFT after reset", resp == `VERIF_BUS_RESP_SOFT);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_amba_mid_reset: pass=%0d expected %0d", pass, TB_EXPECTED_PASS);
    if (fail != 0)
      $fatal(1, "tb_amba_mid_reset failed");
    $display("[SUCCESS] mid-transfer reset OS abort OK");
    $finish;
  end

endmodule
