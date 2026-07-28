// AXI snoop pulse + snq overflow drop lock-down
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"
`include "verif_sim_watchdog.vh"
`include "verif_tb_check.vh"

module tb_axi_snoop_snq;

  localparam integer TB_EXPECTED_PASS = 5;

  `VERIF_SIM_WATCHDOG_NS

  localparam integer DATA_WIDTH = `VERIF_DATA_WIDTH;
  localparam integer AXI_ID_WIDTH = `VERIF_AXI_ID_WIDTH;
  localparam integer OS_MAX = 4;
  localparam integer SNQ_D = 2;  // tiny queue so dual R/B completion forces drops
  localparam [31:0] BASE = 32'hA000_0000;

  reg clk = 0;
  reg aresetn = 0;
  always #5 clk = ~clk;

  wire [DATA_WIDTH-1:0] rdata;
  wire [1:0] rresp, bresp;
  wire        arready, rvalid, rlast, awready, wready, bvalid;
  wire [AXI_ID_WIDTH-1:0] rid, bid;

  wire sn_v, sn_wr;
  wire [31:0] sn_addr, sn_data;

  // Observe snoop pulses
  integer snoop_pulse_n;
  reg     sn_v_d;
  always @(posedge clk or negedge aresetn) begin
    if (!aresetn) begin
      sn_v_d <= 1'b0;
      snoop_pulse_n <= 0;
    end else begin
      if (sn_v && !sn_v_d)
        snoop_pulse_n <= snoop_pulse_n + 1;
      sn_v_d <= sn_v;
    end
  end

  verif_axi_full_master #(
    .AXI_PROT(4),
    .ID_WIDTH(AXI_ID_WIDTH),
    .MAX_OUTSTANDING(OS_MAX),
    .SNQ_DEPTH(SNQ_D)
  ) u_mst (
    .ACLK(clk), .ARESETn(aresetn),
    .ARREADY(arready), .RVALID(rvalid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RID(rid),
    .AWREADY(awready), .WREADY(wready), .BVALID(bvalid), .BRESP(bresp), .BID(bid),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARLOCK(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWLOCK(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(sn_v), .snoop_wr(sn_wr), .snoop_addr(sn_addr), .snoop_data(sn_data)
  );

  verif_axi_full_slave_simple #(
    .BASE(BASE),
    .R_LATENCY(1),
    .B_LATENCY(1),
    .MAX_OUTSTANDING(8),
    .INIT_WORD0(32'h11111111),
    .INIT_WORD1(32'h22222222)
  ) u_slv (
    .ACLK(clk), .ARESETn(aresetn),
    .ARID(u_mst.ARID), .ARADDR(u_mst.ARADDR), .ARLEN(u_mst.ARLEN), .ARSIZE(u_mst.ARSIZE),
    .ARBURST(u_mst.ARBURST), .ARLOCK(u_mst.ARLOCK), .ARVALID(u_mst.ARVALID), .ARREADY(arready),
    .RID(rid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RVALID(rvalid), .RREADY(u_mst.RREADY),
    .AWID(u_mst.AWID), .AWADDR(u_mst.AWADDR), .AWLEN(u_mst.AWLEN), .AWSIZE(u_mst.AWSIZE),
    .AWBURST(u_mst.AWBURST), .AWLOCK(u_mst.AWLOCK), .AWVALID(u_mst.AWVALID), .AWREADY(awready),
    .WID(u_mst.WID), .WDATA(u_mst.WDATA), .WSTRB(u_mst.WSTRB), .WLAST(u_mst.WLAST),
    .WVALID(u_mst.WVALID), .WREADY(wready),
    .BID(bid), .BRESP(bresp), .BVALID(bvalid), .BREADY(u_mst.BREADY)
  );

  integer pass, fail;
  integer h0, h1, h2, h3, n;
  reg ok0, ok1, ok2, ok3;
  reg [31:0] d0, d1, d2, d3;
  reg [1:0]  r0, r1, r2, r3;
  integer drops0, drops1;

  task check;
    input [8*`VERIF_TB_CHECK_NAME_CHARS-1:0] name;
    input         cond;
    begin
      if (cond) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    $dumpfile("sim_build/tb_axi_snoop_snq.vcd");
    $dumpvars(0, tb_axi_snoop_snq);
    repeat (4) @(posedge clk);
    aresetn = 1'b1;
    repeat (2) @(posedge clk);

    $display("tb_axi_snoop_snq: snoop pulse + snq drop (SNQ_DEPTH=%0d)", SNQ_D);
    drops0 = u_mst.snq_drop_count;
    check("snq_drop starts at 0", drops0 == 0);

    // Functional traffic → snoop_valid drain pulses
    u_mst.bus_write_issue(BASE + 0, 32'hA0A0_0000, 3'd4, h0, ok0);
    u_mst.bus_write_issue(BASE + 4, 32'hA0A0_0001, 3'd4, h1, ok1);
    u_mst.bus_read_issue(BASE + 0, 3'd4, h2, ok2);
    u_mst.bus_read_issue(BASE + 4, 3'd4, h3, ok3);
    check("traffic issue", ok0 && ok1 && ok2 && ok3);
    u_mst.bus_write_wait(h0, r0);
    u_mst.bus_write_wait(h1, r1);
    u_mst.bus_read_wait(h2, d0, r2);
    u_mst.bus_read_wait(h3, d1, r3);
    repeat (16) @(posedge clk);
    check("snoop_valid pulsed", snoop_pulse_n > 0);
    check("traffic data OK",
          r0 == `VERIF_BUS_RESP_OK && r1 == `VERIF_BUS_RESP_OK &&
          d0 == 32'hA0A0_0000 && d1 == 32'hA0A0_0001);

    // Direct snq_push flood without intervening clocks → depth overflow
    // (always-block drain only runs on posedge; task pushes are same-time)
    u_mst.snq_push(1'b1, 32'h5001_0001, 32'hD001_0001);
    u_mst.snq_push(1'b1, 32'h5001_0002, 32'hD001_0002);
    u_mst.snq_push(1'b0, 32'h5001_0003, 32'hD001_0003);  // exceeds SNQ_D=2
    drops1 = u_mst.snq_drop_count;
    $display("  [info] snq_drop_count=%0d snoop_pulse_n=%0d", drops1, snoop_pulse_n);
    check("snq drop on push overflow", drops1 > drops0);

    // Let drain flush artificial entries
    repeat (8) @(posedge clk);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_axi_snoop_snq: pass=%0d expected %0d", pass, TB_EXPECTED_PASS);
    if (fail != 0)
      $fatal(1, "tb_axi_snoop_snq failed");
    $display("[SUCCESS] AXI snoop/snq drop OK");
    $finish;
  end

endmodule
