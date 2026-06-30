// iverilog gate — distinct ARID + out-of-order R collect by handle
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"

module tb_axi_id_ooo;

  localparam integer AXI_ID_WIDTH = `VERIF_AXI_ID_WIDTH;
  localparam integer OS_MAX = `VERIF_AXI_MAX_OUTSTANDING;
  localparam [31:0] BASE = 32'hA000_0000;

  reg clk = 0;
  always #5 clk = ~clk;

  wire arready, rvalid, rlast, awready, wready, bvalid;
  wire [`VERIF_DATA_WIDTH-1:0] rdata;
  wire [1:0] rresp;
  wire [AXI_ID_WIDTH-1:0] rid, bid;

  verif_axi_full_master #(
    .AXI_PROT(4),
    .ID_WIDTH(AXI_ID_WIDTH),
    .MAX_OUTSTANDING(OS_MAX)
  ) u_mst (
    .ACLK(clk), .ARESETn(1'b1),
    .ARREADY(arready), .RVALID(rvalid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RID(rid),
    .AWREADY(awready), .WREADY(wready), .BVALID(bvalid), .BRESP(rresp), .BID(bid),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_axi_full_slave_simple #(
    .BASE(BASE),
    .R_LATENCY(8),
    .B_LATENCY(8),
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
    .BID(bid), .BRESP(rresp), .BVALID(bvalid), .BREADY(u_mst.BREADY)
  );

  integer pass, fail;
  integer h0, h1, h2, h3;
  reg ok;
  reg [31:0] d0, d1, d2, d3;
  reg [1:0] r0, r1, r2, r3;
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

    fork
      forever @(posedge clk)
        if (rvalid && u_mst.RREADY && rlast)
          $display("  [trace] R id=%0d data=%08h", rid, rdata);
    join_none

    u_mst.bus_read_issue(BASE + 0,  3'd4, h0, ok);
    check("issue h0", ok && h0 == 0);
    u_mst.bus_read_issue(BASE + 4,  3'd4, h1, ok);
    check("issue h1", ok && h1 == 1);
    u_mst.bus_read_issue(BASE + 16, 3'd4, h2, ok);
    check("issue h2", ok && h2 == 2);
    u_mst.bus_read_issue(BASE + 20, 3'd4, h3, ok);
    check("issue h3", ok && h3 == 3);
    check("handles are distinct IDs", h0 != h1 && h1 != h2 && h2 != h3);

    // Collect out-of-order by handle (not issue order)
    u_mst.bus_read_wait(h3, d3, r3);
    u_mst.bus_read_wait(h1, d1, r1);
    u_mst.bus_read_wait(h0, d0, r0);
    u_mst.bus_read_wait(h2, d2, r2);

    check("id0 data BASE+0",  d0 == 32'h11111111);
    check("id1 data BASE+4",  d1 == 32'h0);
    check("id2 data BASE+16", d2 == 32'h22222222);
    check("id3 data BASE+20", d3 == 32'h0);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "tb_axi_id_ooo FAILED");
    $display("[SUCCESS] iverilog ID + OOO collect OK");
    $finish;
  end

endmodule