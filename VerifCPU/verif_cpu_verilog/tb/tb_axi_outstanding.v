// AXI full multiple-outstanding + latency slave — performance model smoke
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"

module tb_axi_outstanding;

  localparam integer DATA_WIDTH = `VERIF_DATA_WIDTH;
  localparam integer AXI_ID_WIDTH = `VERIF_AXI_ID_WIDTH;
  localparam integer OS_MAX = 4;
  localparam integer R_LAT = 32;
  localparam [31:0] BASE = 32'hA000_0000;

  reg clk = 0;
  always #5 clk = ~clk;

  wire [DATA_WIDTH-1:0] rdata;
  wire [1:0] rresp, bresp;
  wire        arready, rvalid, rlast, awready, wready, bvalid;
  wire [AXI_ID_WIDTH-1:0] rid, bid;

  verif_axi_full_master #(
    .AXI_PROT(4),
    .ID_WIDTH(AXI_ID_WIDTH),
    .MAX_OUTSTANDING(OS_MAX)
  ) u_mst (
    .ACLK(clk), .ARESETn(1'b1),
    .ARREADY(arready), .RVALID(rvalid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RID(rid),
    .AWREADY(awready), .WREADY(wready), .BVALID(bvalid), .BRESP(bresp), .BID(bid),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_axi_full_slave_simple #(
    .BASE(BASE),
    .R_LATENCY(R_LAT),
    .B_LATENCY(R_LAT),
    .MAX_OUTSTANDING(8),
    .ENABLE_R_REORDER(1'b1),
    .INIT_WORD0(32'h11111111),
    .INIT_WORD1(32'h22222222)
  ) u_slv (
    .ACLK(clk), .ARESETn(1'b1),
    .ARID(u_mst.ARID), .ARADDR(u_mst.ARADDR), .ARLEN(u_mst.ARLEN), .ARSIZE(u_mst.ARSIZE),
    .ARBURST(u_mst.ARBURST), .ARVALID(u_mst.ARVALID), .ARREADY(arready),
    .RID(rid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RVALID(rvalid), .RREADY(u_mst.RREADY),
    .AWID(u_mst.AWID), .AWADDR(u_mst.AWADDR), .AWLEN(u_mst.AWLEN), .AWSIZE(u_mst.AWSIZE),
    .AWBURST(u_mst.AWBURST), .AWVALID(u_mst.AWVALID), .AWREADY(awready),
    .WID(u_mst.WID), .WDATA(u_mst.WDATA), .WSTRB(u_mst.WSTRB), .WLAST(u_mst.WLAST),
    .WVALID(u_mst.WVALID), .WREADY(wready),
    .BID(bid), .BRESP(bresp), .BVALID(bvalid), .BREADY(u_mst.BREADY)
  );

  integer pass, fail;
  integer c0, c1, seq_cycles, os_cycles, n;
  integer h0, h1, h2, h3, hx;
  reg ok, okx;
  reg [31:0] d0, d1, d2, d3, rd;
  reg [1:0]  r0, r1, r2, r3;

  task check;
    input [8*128:1] name;
    input cond;
    begin
      if (cond) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    @(posedge clk);
    @(posedge clk);

    // Sequential baseline — same 4 addresses as outstanding burst
    c0 = $time;
    u_mst.bus_read(BASE + 0, 3'd4, d0, r0);
    u_mst.bus_read(BASE + 16, 3'd4, d2, r2);
    u_mst.bus_read(BASE + 4, 3'd4, d1, r1);
    u_mst.bus_read(BASE + 20, 3'd4, d3, r3);
    c1 = $time;
    seq_cycles = (c1 - c0) / 10;

    check("sequential data",
          d0 == 32'h11111111 && d2 == 32'h22222222 && d1 == 32'h0 && d3 == 32'h0);

    // Outstanding burst
    c0 = $time;
    u_mst.bus_read_issue(BASE + 0, 3'd4, h0, ok);
    u_mst.bus_read_issue(BASE + 16, 3'd4, h2, ok);
    u_mst.bus_read_issue(BASE + 4, 3'd4, h1, ok);
    u_mst.bus_read_issue(BASE + 20, 3'd4, h3, ok);
    // Collect out-of-issue-order (reorder slave may complete h2 before h0)
    u_mst.bus_read_wait(h2, d2, r2);
    u_mst.bus_read_wait(h0, d0, r0);
    u_mst.bus_read_wait(h1, d1, r1);
    u_mst.bus_read_wait(h3, d3, r3);
    c1 = $time;
    os_cycles = (c1 - c0) / 10;

    $display("  [perf] sequential_cycles=%0d outstanding_cycles=%0d", seq_cycles, os_cycles);
    check("outstanding faster", os_cycles < seq_cycles);
    check("outstanding data",
          d0 == 32'h11111111 && d2 == 32'h22222222 && d1 == 32'h0 && d3 == 32'h0);
    check("reorder by handle", d2 == 32'h22222222 && d0 == 32'h11111111);

    // Outstanding write + readback
    u_mst.bus_write_issue(BASE + 32, 32'hA5A5A5A5, 3'd4, h0, ok);
    u_mst.bus_write_wait(h0, r0);
    u_mst.bus_read(BASE + 32, 3'd4, rd, r0);
    check("outstanding write", rd == 32'hA5A5A5A5);

    // Slot full
    u_mst.bus_read_issue(BASE + 0, 3'd4, h0, ok);
    u_mst.bus_read_issue(BASE + 4, 3'd4, h1, ok);
    u_mst.bus_read_issue(BASE + 16, 3'd4, h2, ok);
    u_mst.bus_read_issue(BASE + 20, 3'd4, h3, ok);
    u_mst.bus_read_issue(BASE + 32, 3'd4, hx, okx);
    check("slot full reject", !okx);
    u_mst.bus_read_wait(h0, d0, r0);
    u_mst.bus_read_wait(h1, d1, r1);
    u_mst.bus_read_wait(h2, d2, r2);
    u_mst.bus_read_wait(h3, d3, r3);

    u_mst.bus_read_outstanding_count(n);
    $display("  [perf] os_rd_inflight_end=%0d seq=%0d os=%0d speedup=%0d",
             n, seq_cycles, os_cycles, seq_cycles - os_cycles);
    check("perf speedup margin", (seq_cycles - os_cycles) >= 4);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "tb_axi_outstanding FAILED");
    $display("[SUCCESS] AXI multiple-outstanding perf smoke OK");
    $finish;
  end

endmodule