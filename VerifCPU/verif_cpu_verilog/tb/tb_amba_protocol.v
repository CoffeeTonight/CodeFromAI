// Protocol regression: AHB error, AXI SLVERR, burst, 2-master arbiter, AWATOP smoke
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"
`include "verif_sim_watchdog.vh"

module tb_amba_protocol;

  localparam integer TB_EXPECTED_PASS = 40;

  `VERIF_SIM_WATCHDOG_NS

  reg clk = 0;
  reg rstn = 0;
  always #5 clk = ~clk;

  wire [31:0] ahb_rdata;
  wire        ahb_ro;
  wire [1:0]  ahb_resp;

  wire [31:0] axi_rdata;
  wire [3:0]  axi_rid, axi_bid;
  wire        axi_arready, axi_rvalid, axi_awready, axi_wready, axi_bvalid, axi_rlast;
  wire [1:0]  axi_rresp, axi_bresp;

  wire [31:0] axi_b_rdata;
  wire [3:0]  axi_b_rid, axi_b_bid;
  wire        axi_b_arready, axi_b_rvalid, axi_b_awready, axi_b_wready, axi_b_bvalid, axi_b_rlast;
  wire [1:0]  axi_b_rresp, axi_b_bresp;

  wire [3:0]  s_arid, s_awid;
  wire [31:0] s_araddr, s_awaddr, s_wdata, arb_rdata;
  wire [7:0]  s_arlen, s_awlen;
  wire [2:0]  s_arsize, s_awsize;
  wire [1:0]  s_arburst, s_awburst;
  wire        s_arlock, s_awlock;
  wire [5:0]  s_awatop;
  wire [3:0]  s_wstrb;
  wire        s_arvalid, s_awvalid, s_wvalid, s_wlast, s_bready, s_rready;
  wire [3:0]  arb_rid, arb_bid;
  wire        arb_arready, arb_rvalid, arb_awready, arb_wready, arb_bvalid, arb_rlast;
  wire [1:0]  arb_rresp, arb_bresp;

  verif_ahb_lite_master u_ahb (
    .HCLK(clk), .HRESETn(rstn),
    .HRDATA(ahb_rdata), .HREADY(ahb_ro), .HRESP(ahb_resp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_ahb_lite_slave_simple #(.BASE(32'h8000_0000), .SIZE(32'h1000)) u_ahb_s (
    .HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahb.HADDR), .HSIZE(u_ahb.HSIZE), .HTRANS(u_ahb.HTRANS),
    .HWRITE(u_ahb.HWRITE), .HWDATA(u_ahb.HWDATA), .HREADY(1'b1),
    .HRDATA(ahb_rdata), .HREADYOUT(ahb_ro), .HRESP(ahb_resp)
  );

  verif_axi_full_master #(.AXI_PROT(4), .ID_BASE(0), .MAX_OUTSTANDING(2)) u_axi (
    .ACLK(clk), .ARESETn(rstn),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARLOCK(), .ARVALID(), .ARREADY(axi_arready),
    .RID(axi_rid), .RDATA(axi_rdata), .RRESP(axi_rresp), .RLAST(axi_rlast), .RVALID(axi_rvalid), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWLOCK(), .AWVALID(), .AWREADY(axi_awready),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .WREADY(axi_wready),
    .BID(axi_bid), .BRESP(axi_bresp), .BVALID(axi_bvalid), .BREADY(),
    .AWQOS(), .AWREGION(), .AWATOP(),
    .ARQOS(), .ARREGION(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_axi_full_master #(.AXI_PROT(4), .ID_BASE(8), .MAX_OUTSTANDING(1)) u_axi_b (
    .ACLK(clk), .ARESETn(rstn),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARLOCK(), .ARVALID(), .ARREADY(axi_b_arready),
    .RID(axi_b_rid), .RDATA(axi_b_rdata), .RRESP(axi_b_rresp), .RLAST(axi_b_rlast),
    .RVALID(axi_b_rvalid), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWLOCK(), .AWVALID(), .AWREADY(axi_b_awready),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .WREADY(axi_b_wready),
    .BID(axi_b_bid), .BRESP(axi_b_bresp), .BVALID(axi_b_bvalid), .BREADY(),
    .AWQOS(), .AWREGION(), .AWATOP(),
    .ARQOS(), .ARREGION(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_axi_arbiter_2m1s u_arb (
    .ACLK(clk), .ARESETn(rstn),
    .M0_ARID(u_axi.ARID), .M0_ARADDR(u_axi.ARADDR), .M0_ARLEN(u_axi.ARLEN),
    .M0_ARSIZE(u_axi.ARSIZE), .M0_ARBURST(u_axi.ARBURST), .M0_ARLOCK(u_axi.ARLOCK),
    .M0_ARVALID(u_axi.ARVALID),
    .M0_ARREADY(axi_arready),
    .M0_AWID(u_axi.AWID), .M0_AWADDR(u_axi.AWADDR), .M0_AWLEN(u_axi.AWLEN),
    .M0_AWSIZE(u_axi.AWSIZE), .M0_AWBURST(u_axi.AWBURST), .M0_AWLOCK(u_axi.AWLOCK),
    .M0_AWATOP(u_axi.AWATOP),
    .M0_AWVALID(u_axi.AWVALID), .M0_AWREADY(axi_awready),
    .M0_WDATA(u_axi.WDATA), .M0_WSTRB(u_axi.WSTRB), .M0_WLAST(u_axi.WLAST),
    .M0_WVALID(u_axi.WVALID), .M0_WREADY(axi_wready),
    .M0_BID(axi_bid), .M0_BRESP(axi_bresp), .M0_BVALID(axi_bvalid), .M0_BREADY(u_axi.BREADY),
    .M0_RID(axi_rid), .M0_RDATA(axi_rdata), .M0_RRESP(axi_rresp), .M0_RLAST(axi_rlast),
    .M0_RVALID(axi_rvalid), .M0_RREADY(u_axi.RREADY),
    .M1_ARID(u_axi_b.ARID), .M1_ARADDR(u_axi_b.ARADDR), .M1_ARLEN(u_axi_b.ARLEN),
    .M1_ARSIZE(u_axi_b.ARSIZE), .M1_ARBURST(u_axi_b.ARBURST), .M1_ARLOCK(u_axi_b.ARLOCK),
    .M1_ARVALID(u_axi_b.ARVALID),
    .M1_ARREADY(axi_b_arready),
    .M1_AWID(u_axi_b.AWID), .M1_AWADDR(u_axi_b.AWADDR), .M1_AWLEN(u_axi_b.AWLEN),
    .M1_AWSIZE(u_axi_b.AWSIZE), .M1_AWBURST(u_axi_b.AWBURST), .M1_AWLOCK(u_axi_b.AWLOCK),
    .M1_AWATOP(u_axi_b.AWATOP),
    .M1_AWVALID(u_axi_b.AWVALID), .M1_AWREADY(axi_b_awready),
    .M1_WDATA(u_axi_b.WDATA), .M1_WSTRB(u_axi_b.WSTRB), .M1_WLAST(u_axi_b.WLAST),
    .M1_WVALID(u_axi_b.WVALID), .M1_WREADY(axi_b_wready),
    .M1_BID(axi_b_bid), .M1_BRESP(axi_b_bresp), .M1_BVALID(axi_b_bvalid), .M1_BREADY(u_axi_b.BREADY),
    .M1_RID(axi_b_rid), .M1_RDATA(axi_b_rdata), .M1_RRESP(axi_b_rresp), .M1_RLAST(axi_b_rlast),
    .M1_RVALID(axi_b_rvalid), .M1_RREADY(u_axi_b.RREADY),
    .S_ARID(s_arid), .S_ARADDR(s_araddr), .S_ARLEN(s_arlen), .S_ARSIZE(s_arsize),
    .S_ARBURST(s_arburst), .S_ARLOCK(s_arlock), .S_ARVALID(s_arvalid), .S_ARREADY(arb_arready),
    .S_AWID(s_awid), .S_AWADDR(s_awaddr), .S_AWLEN(s_awlen), .S_AWSIZE(s_awsize),
    .S_AWBURST(s_awburst), .S_AWLOCK(s_awlock), .S_AWATOP(s_awatop), .S_AWVALID(s_awvalid),
    .S_AWREADY(arb_awready),
    .S_WDATA(s_wdata), .S_WSTRB(s_wstrb), .S_WLAST(s_wlast), .S_WVALID(s_wvalid),
    .S_WREADY(arb_wready),
    .S_BID(arb_bid), .S_BRESP(arb_bresp), .S_BVALID(arb_bvalid), .S_BREADY(s_bready),
    .S_RID(arb_rid), .S_RDATA(arb_rdata), .S_RRESP(arb_rresp), .S_RLAST(arb_rlast),
    .S_RVALID(arb_rvalid), .S_RREADY(s_rready)
  );

  verif_axi_full_slave_simple #(
    .BASE(32'hA000_0000), .SIZE(32'h1000),
    .INIT_WORD0(32'hBADC0DE1), .INIT_WORD1(32'hBADC0DE2)
  ) u_axi_s (
    .ACLK(clk), .ARESETn(rstn),
    .ARID(s_arid), .ARADDR(s_araddr), .ARLEN(s_arlen), .ARSIZE(s_arsize),
    .ARBURST(s_arburst), .ARLOCK(s_arlock), .ARVALID(s_arvalid), .ARREADY(arb_arready),
    .RID(arb_rid), .RDATA(arb_rdata), .RRESP(arb_rresp), .RLAST(arb_rlast),
    .RVALID(arb_rvalid), .RREADY(s_rready),
    .AWID(s_awid), .AWADDR(s_awaddr), .AWLEN(s_awlen), .AWSIZE(s_awsize),
    .AWBURST(s_awburst), .AWLOCK(s_awlock), .AWVALID(s_awvalid), .AWREADY(arb_awready),
    .WID(4'd0), .WDATA(s_wdata), .WSTRB(s_wstrb), .WLAST(s_wlast),
    .WVALID(s_wvalid), .WREADY(arb_wready),
    .BID(arb_bid), .BRESP(arb_bresp), .BVALID(arb_bvalid), .BREADY(s_bready)
  );

  reg [31:0] rd;
  reg [31:0] d0, d1, d2, d3;
  reg [31:0] dual0, dual1;
  reg [31:0] mm0, mm1;
  reg [1:0]  resp;
  reg [1:0]  resp0, resp1;
  reg [1:0]  mm_resp0, mm_resp1;
  reg        dual_ok;
  reg        had_err;
  reg        had_dec;
  reg        w_slverr;
  reg        w_decerr;
  reg        lock_seen;
  reg        mm_ok0, mm_ok1;
  integer    beat_n;
  integer    bi;
  integer    h0, h1;
  integer    wh0, wh1;
  integer pass, fail;

  always @(posedge clk)
    if (s_arvalid && arb_arready && s_arlock)
      lock_seen <= 1'b1;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    pass = 0; fail = 0;
    lock_seen = 1'b0;
    repeat (4) @(posedge clk);
    rstn = 1'b1;
    repeat (2) @(posedge clk);
    $display("tb_amba_protocol: AHB + AXI arbiter + burst + AWATOP");

    u_ahb.bus_read(32'h8000_2000, 3'd4, rd, resp);
    check("AHB OOB read ERROR", resp == 2'd2);

    u_axi.bus_read(32'hA000_2000, 3'd4, rd, resp);
    check("AXI OOB read SLVERR", resp == 2'd2);

    u_axi.bus_read(32'hA000_0800, 3'd4, rd, resp);
    check("AXI in-range DECERR read", resp == 2'd3);

    u_axi.bus_write(32'hA000_2000, 32'hDEAD_BEEF, 3'd4, resp);
    check("AXI OOB write SLVERR", resp == 2'd2);

    u_axi.bus_write(32'hA000_0804, 32'hDEAD_BEEF, 3'd4, resp);
    check("AXI in-range DECERR write", resp == 2'd3);

    u_axi.bus_write(32'hA000_0FFC, 32'h11111111, 3'd4, resp);
    check("AXI in-range last-word write OK", resp == 2'd0);
    u_axi.bus_read(32'hA000_0FFC, 3'd4, rd, resp);
    check("AXI in-range last-word readback", resp == 2'd0 && rd == 32'h11111111);

    u_axi.bus_read(32'hA000_1000, 3'd4, rd, resp);
    check("AXI 4KiB page+1 read SLVERR", resp == 2'd2);

    u_axi.bus_write(32'hA000_0000, 32'h11111111, 3'd4, resp);
    u_axi.bus_write(32'hA000_0004, 32'h22222222, 3'd4, resp);
    u_axi.bus_write(32'hA000_0008, 32'h33333333, 3'd4, resp);
    u_axi.bus_write(32'hA000_000C, 32'h44444444, 3'd4, resp);
    u_axi.bus_read_incr(32'hA000_0000, 8'd3, 3'd4, 2'b01, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI INCR4 read beat count", beat_n == 4 && resp == 2'd0);
    check("AXI INCR4 read data pattern",
          d0 == 32'h11111111 && d1 == 32'h22222222 &&
          d2 == 32'h33333333 && d3 == 32'h44444444);

    u_axi.bus_write_incr(32'hA000_0060, 8'd3, 3'd4, 2'b01, 32'hC100_0000, resp, w_slverr, w_decerr);
    check("AXI INCR4 write OK", resp == 2'd0 && !w_slverr && !w_decerr);
    u_axi.bus_read_incr(32'hA000_0060, 8'd3, 3'd4, 2'b01, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI INCR4 write readback",
          d0 == 32'hC100_0000 && d1 == 32'hC100_0001 &&
          d2 == 32'hC100_0002 && d3 == 32'hC100_0003);

    u_axi.bus_write_incr(32'hA000_0FFC, 8'd3, 3'd4, 2'b01, 32'hD000_0000, resp, w_slverr, w_decerr);
    check("AXI INCR4 write 4KiB page cross SLVERR", w_slverr && resp == 2'd2);

    for (bi = 0; bi < 8; bi = bi + 1)
      u_axi.bus_write(32'hA000_0020 + (bi * 4), 32'hA000_0020 + bi, 3'd4, resp);
    u_axi.bus_read_incr(32'hA000_0020, 8'd7, 3'd4, 2'b01, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI INCR8 read beat count", beat_n == 8 && resp == 2'd0 && !had_err && !had_dec);
    u_axi.bus_read(32'hA000_0028, 3'd4, rd, resp);
    check("AXI INCR8 beat2 data spot", resp == 2'd0 && rd == 32'hA000_0022);

    for (bi = 0; bi < 16; bi = bi + 1)
      u_axi.bus_write(32'hA000_0040 + (bi * 4), 32'hB000_0000 + bi, 3'd4, resp);
    u_axi.bus_read_incr(32'hA000_0040, 8'd15, 3'd4, 2'b01, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI INCR16 read beat count", beat_n == 16 && resp == 2'd0 && !had_err && !had_dec);

    u_axi.bus_read_incr(32'hA000_0FFC, 8'd3, 3'd4, 2'b01, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI INCR4 4KiB page cross SLVERR", had_err && beat_n >= 2);

    u_axi.bus_read_incr(32'hA000_0800, 8'd3, 3'd4, 2'b01, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI INCR4 DECERR mid-burst", had_dec && beat_n >= 1);

    u_axi.bus_read_dual_outstanding(32'hA000_0000, 32'hA000_000C, 3'd4,
                                    dual0, dual1, resp0, resp1, dual_ok);
    check("AXI dual-outstanding read OK",
          dual_ok && resp0 == 2'd0 && resp1 == 2'd0 &&
          dual0 == 32'h11111111 && dual1 == 32'h44444444);

    u_axi.bus_write(32'hA000_0008, 32'hA008_0008, 3'd4, resp);
    u_axi.bus_write(32'hA000_000C, 32'hA00C_000C, 3'd4, resp);
    u_axi.bus_write(32'hA000_0010, 32'hA010_0010, 3'd4, resp);
    u_axi.bus_write(32'hA000_0014, 32'hA014_0014, 3'd4, resp);
    u_axi.bus_read(32'hA000_0010, 3'd4, rd, resp);
    check("WRAP prep @0x10", resp == 2'd0 && rd == 32'hA010_0010);
    u_axi.bus_read_incr(32'hA000_000C, 8'd3, 3'd4, 2'b10, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI WRAP4 read beat count", beat_n == 4 && resp == 2'd0);
    check("AXI WRAP4 start beat data", d0 == 32'hA00C_000C);
    check("AXI WRAP4 wrap endpoint data", d3 == 32'hA008_0008);
    u_axi.bus_read(32'hA000_0010, 3'd4, rd, resp);
    check("AXI WRAP4 mid-beat @0x10", resp == 2'd0 && rd == 32'hA010_0010);

    u_axi.bus_write_incr(32'hA000_002C, 8'd3, 3'd4, 2'b10, 32'hF020_002C, resp, w_slverr, w_decerr);
    check("AXI WRAP4 write OK", resp == 2'd0 && !w_slverr && !w_decerr);
    u_axi.bus_read_incr(32'hA000_002C, 8'd3, 3'd4, 2'b10, d0, d1, d2, d3, resp, beat_n, had_err, had_dec);
    check("AXI WRAP4 write readback",
          beat_n == 4 && resp == 2'd0 &&
          d0 == 32'hF020_002C && d1 == 32'hF020_002D &&
          d2 == 32'hF020_002E && d3 == 32'hF020_002F);

    u_axi.bus_write(32'hA000_0100, 32'hA0A0_A0A0, 3'd4, resp);
    u_axi_b.bus_write(32'hA000_0104, 32'hB1B1_B1B1, 3'd4, resp);
    u_axi.bus_read_issue(32'hA000_0100, 3'd4, h0, mm_ok0);
    u_axi_b.bus_read_issue(32'hA000_0104, 3'd4, h1, mm_ok1);
    check("2-master arbiter concurrent issue", mm_ok0 && mm_ok1);
    u_axi.bus_read_wait(h0, mm0, mm_resp0);
    u_axi_b.bus_read_wait(h1, mm1, mm_resp1);
    check("2-master M0 read data", mm_resp0 == 2'd0 && mm0 == 32'hA0A0_A0A0);
    check("2-master M1 read data", mm_resp1 == 2'd0 && mm1 == 32'hB1B1_B1B1);

    u_axi.bus_write_issue(32'hA000_0140, 32'hE0E0_E0E0, 3'd4, wh0, mm_ok0);
    u_axi_b.bus_write_issue(32'hA000_0144, 32'hF0F0_F0F0, 3'd4, wh1, mm_ok1);
    check("2-master concurrent AW issue", mm_ok0 && mm_ok1);
    u_axi.bus_write_wait(wh0, mm_resp0);
    u_axi_b.bus_write_wait(wh1, mm_resp1);
    u_axi.bus_read(32'hA000_0140, 3'd4, mm0, mm_resp0);
    u_axi_b.bus_read(32'hA000_0144, 3'd4, mm1, mm_resp1);
    check("2-master concurrent AW data M0", mm_resp0 == 2'd0 && mm0 == 32'hE0E0_E0E0);
    check("2-master concurrent AW data M1", mm_resp1 == 2'd0 && mm1 == 32'hF0F0_F0F0);

    u_axi.bus_write(32'hA000_0120, 32'hC0C0_C0C0, 3'd4, resp);
    u_axi_b.bus_write(32'hA000_0124, 32'hD0D0_D0D0, 3'd4, resp);
    u_axi.bus_read(32'hA000_0120, 3'd4, mm0, mm_resp0);
    u_axi_b.bus_read(32'hA000_0124, 3'd4, mm1, mm_resp1);
    check("2-master AW ordering M0 data", mm_resp0 == 2'd0 && mm0 == 32'hC0C0_C0C0);
    check("2-master AW ordering M1 data", mm_resp1 == 2'd0 && mm1 == 32'hD0D0_D0D0);

    check("AXI ARLOCK idle tied 0", u_axi.ARLOCK == 1'b0);
    u_axi.bus_read_locked(32'hA000_0200, 3'd4, 1'b1, rd, resp);
    check("AXI ARLOCK locked read OK", resp == 2'd0);
    check("AXI ARLOCK propagated to slave", lock_seen);
    check("AXI AWLOCK idle tied 0", u_axi.AWLOCK == 1'b0 && s_awlock == 1'b0);

    u_axi.bus_write_exclusive(32'hA000_0180, 32'h0E0C1001, 3'd4, resp);
    check("AXI AWATOP exclusive store OK", resp == 2'd0);
    u_axi.bus_read(32'hA000_0180, 3'd4, rd, resp);
    check("AXI AWATOP exclusive readback", resp == 2'd0 && rd == 32'h0E0C1001);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_amba_protocol: pass=%0d expected %0d", pass, TB_EXPECTED_PASS);
    if (fail != 0) $fatal(1, "tb_amba_protocol failed");
    $display("[SUCCESS] AMBA protocol smoke OK");
    $finish;
  end

endmodule