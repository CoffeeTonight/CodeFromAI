// Negative / contract lock-down paths for recent AMBA hardening
// Locks: AHB5/full OOB ERROR, dual-write integrity, split early-stop on SLV,
//        illegal size, OS unaligned reject, double-wait / free-wait SOFT
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"
`include "verif_sim_watchdog.vh"

module tb_amba_neg_paths;

  // Keep in sync with check() calls below
  localparam integer TB_EXPECTED_PASS = 23;

  `VERIF_SIM_WATCHDOG_NS

  reg clk = 0;
  reg rstn = 0;
  always #5 clk = ~clk;

  // --- AHB-Lite ---
  wire [31:0] ahb_rdata;
  wire        ahb_hready;
  wire [1:0]  ahb_hresp;

  verif_ahb_lite_master u_ahb (
    .HCLK(clk), .HRESETn(rstn),
    .HRDATA(ahb_rdata), .HREADY(ahb_hready), .HRESP(ahb_hresp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );
  verif_ahb_lite_slave_simple #(.BASE(32'h8000_0000), .SIZE(32'h1000),
      .INIT_WORD0(32'h1111_0000), .INIT_WORD1(32'h2222_0000)) u_ahb_s (
    .HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahb.HADDR), .HSIZE(u_ahb.HSIZE), .HTRANS(u_ahb.HTRANS),
    .HWRITE(u_ahb.HWRITE), .HWDATA(u_ahb.HWDATA), .HREADY(ahb_hready),
    .HRDATA(ahb_rdata), .HREADYOUT(ahb_hready), .HRESP(ahb_hresp)
  );

  // --- AHB5-Lite (same ERROR slave class) ---
  wire [31:0] ahb5_rdata;
  wire        ahb5_hready;
  wire [1:0]  ahb5_hresp;

  verif_ahb5_lite_master u_ahb5 (
    .HCLK(clk), .HRESETn(rstn),
    .HRDATA(ahb5_rdata), .HREADY(ahb5_hready), .HRESP(ahb5_hresp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),
    .HNONSEC(), .HEXCL(), .HEXOK(1'b1),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );
  verif_ahb_lite_slave_simple #(.BASE(32'h8100_0000), .SIZE(32'h1000),
      .INIT_WORD0(32'h3333_0000), .INIT_WORD1(32'h0)) u_ahb5_s (
    .HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahb5.HADDR), .HSIZE(u_ahb5.HSIZE), .HTRANS(u_ahb5.HTRANS),
    .HWRITE(u_ahb5.HWRITE), .HWDATA(u_ahb5.HWDATA), .HREADY(ahb5_hready),
    .HRDATA(ahb5_rdata), .HREADYOUT(ahb5_hready), .HRESP(ahb5_hresp)
  );

  // --- AHB full ---
  wire [31:0] ahbf_rdata;
  wire        ahbf_hready;
  wire [1:0]  ahbf_hresp;

  verif_ahb_master #(.MAX_OUTSTANDING(4)) u_ahbf (
    .HCLK(clk), .HRESETn(rstn),
    .HRDATA(ahbf_rdata), .HREADY(ahbf_hready), .HRESP(ahbf_hresp),
    .HADDR(), .HSIZE(), .HTRANS(), .HBURST(), .HPROT(), .HMASTLOCK(),
    .HWRITE(), .HWDATA(), .HNONSEC(), .HEXCL(), .HEXOK(1'b1),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );
  verif_ahb_lite_slave_simple #(.BASE(32'h8200_0000), .SIZE(32'h1000),
      .INIT_WORD0(32'h4444_0000), .INIT_WORD1(32'h5555_0000)) u_ahbf_s (
    .HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahbf.HADDR), .HSIZE(u_ahbf.HSIZE), .HTRANS(u_ahbf.HTRANS),
    .HWRITE(u_ahbf.HWRITE), .HWDATA(u_ahbf.HWDATA), .HREADY(ahbf_hready),
    .HRDATA(ahbf_rdata), .HREADYOUT(ahbf_hready), .HRESP(ahbf_hresp)
  );

  // --- AXI full (size/align + split OOB) ---
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
  verif_axi_full_slave_simple #(.BASE(32'hA000_0000), .SIZE(32'h1000),
      .INIT_WORD0(32'h0000_00A0), .INIT_WORD1(32'h0)) u_axi_s (
    .ACLK(clk), .ARESETn(rstn),
    .ARID(u_axi.ARID), .ARADDR(u_axi.ARADDR), .ARLEN(u_axi.ARLEN),
    .ARSIZE(u_axi.ARSIZE), .ARBURST(u_axi.ARBURST), .ARLOCK(u_axi.ARLOCK),
    .ARVALID(u_axi.ARVALID), .ARREADY(axi_arready),
    .RID(axi_rid), .RDATA(axi_rdata), .RRESP(axi_rresp), .RLAST(axi_rlast),
    .RVALID(axi_rvalid), .RREADY(u_axi.RREADY),
    .AWID(u_axi.AWID), .AWADDR(u_axi.AWADDR), .AWLEN(u_axi.AWLEN),
    .AWSIZE(u_axi.AWSIZE), .AWBURST(u_axi.AWBURST), .AWLOCK(u_axi.AWLOCK),
    .AWVALID(u_axi.AWVALID), .AWREADY(axi_awready),
    .WID(u_axi.WID), .WDATA(u_axi.WDATA), .WSTRB(u_axi.WSTRB), .WLAST(u_axi.WLAST),
    .WVALID(u_axi.WVALID), .WREADY(axi_wready),
    .BID(axi_bid), .BRESP(axi_bresp), .BVALID(axi_bvalid), .BREADY(u_axi.BREADY)
  );

  // --- APB3 blocking OS (double-wait / free-wait) ---
  wire [31:0] apb_rdata;
  wire        apb_ready, apb_slverr;

  verif_apb_master u_apb (
    .PCLK(clk), .PRESETn(rstn),
    .PRDATA(apb_rdata), .PREADY(apb_ready), .PSLVERR(apb_slverr),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );
  verif_apb_slave_simple #(.BASE(32'h4000_0000), .SIZE(32'h1000)) u_apb_s (
    .PCLK(clk), .PRESETn(rstn),
    .PADDR(u_apb.PADDR), .PSEL(u_apb.PSEL), .PENABLE(u_apb.PENABLE),
    .PWRITE(u_apb.PWRITE), .PWDATA(u_apb.PWDATA), .PSTRB(u_apb.PSTRB),
    .PRDATA(apb_rdata), .PREADY(apb_ready), .PSLVERR(apb_slverr)
  );

  integer pass, fail;
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

  reg [31:0] rd, d0, d1, d_poll, d_wait;
  reg [1:0]  resp, r0, r1, r_poll, r_wait;
  reg        ok, ok0, ok1, done;
  integer    h, h0, h1;

  initial begin
    pass = 0;
    fail = 0;
    repeat (4) @(posedge clk);
    rstn = 1'b1;
    repeat (2) @(posedge clk);
    $display("tb_amba_neg_paths: contract lock-down (OOB / dual-write / split / size / OS SOFT)");

    // --- V1/V2/V3: OOB ERROR on AHB lite / AHB5 / AHB full ---
    u_ahb.bus_read(32'h8000_2000, 3'd4, rd, resp);
    check("AHB-Lite OOB read SLV", resp == `VERIF_BUS_RESP_SLV);

    u_ahb5.bus_read(32'h8100_2000, 3'd4, rd, resp);
    check("AHB5-Lite OOB read SLV", resp == `VERIF_BUS_RESP_SLV);

    u_ahbf.bus_read(32'h8200_2000, 3'd4, rd, resp);
    check("AHB full OOB read SLV", resp == `VERIF_BUS_RESP_SLV);

    // --- V4: AHB full dual write integrity ---
    begin : ahbf_dual_wr
      u_ahbf.bus_write_issue(32'h8200_0040, 32'hA0A0_0001, 3'd4, h0, ok0);
      u_ahbf.bus_write_issue(32'h8200_0044, 32'hB0B0_0002, 3'd4, h1, ok1);
      check("AHB full dual write issue", ok0 && ok1 && h0 != h1);
      u_ahbf.bus_write_wait(h0, r0);
      u_ahbf.bus_write_wait(h1, r1);
      check("AHB full dual write resp", r0 == `VERIF_BUS_RESP_OK && r1 == `VERIF_BUS_RESP_OK);
      u_ahbf.bus_read(32'h8200_0040, 3'd4, d0, resp);
      u_ahbf.bus_read(32'h8200_0044, 3'd4, d1, resp);
      check("AHB full dual write data",
            d0 == 32'hA0A0_0001 && d1 == 32'hB0B0_0002);
    end

    // --- V5: dual write then read (no HWDATA pollution) ---
    begin : ahbf_wr_rd
      u_ahbf.bus_write_issue(32'h8200_0050, 32'hC0C0_00AA, 3'd4, h0, ok0);
      u_ahbf.bus_read_issue(32'h8200_0050, 3'd4, h1, ok1);
      check("AHB full write+read issue", ok0 && ok1);
      u_ahbf.bus_write_wait(h0, r0);
      u_ahbf.bus_read_wait(h1, d1, r1);
      check("AHB full write+read data",
            r0 == `VERIF_BUS_RESP_OK && r1 == `VERIF_BUS_RESP_OK &&
            d1 == 32'hC0C0_00AA);
    end

    // --- V6: unaligned word write near end — early-stop, only in-window byte ---
    // BASE+0xFFF is last byte; size=4 unaligned → first byte OK, rest OOB SLV stop
    u_ahb.bus_write(32'h8000_0FFF, 32'hAABB_CCDD, 3'd4, resp);
    check("split OOB write hard resp",
          resp == `VERIF_BUS_RESP_SLV || resp == `VERIF_BUS_RESP_DEC);
    u_ahb.bus_read(32'h8000_0FFF, 3'd1, rd, resp);
    check("split OOB first byte stored",
          resp == `VERIF_BUS_RESP_OK && rd[7:0] == 8'hDD);
    // Neighbor word low bytes must not get later split beats (would be CC at FFFE etc.)
    u_ahb.bus_read(32'h8000_0FFC, 3'd4, rd, resp);
    check("split OOB no spurious mid-word store",
          resp == `VERIF_BUS_RESP_OK && rd[23:16] == 8'h00 && rd[15:8] == 8'h00);

    // --- V7: illegal size ---
    u_axi.bus_read_issue(32'hA000_0000, 3'd0, h, ok);
    check("AXI OS issue size=0 reject", !ok);
    u_axi.bus_read_issue(32'hA000_0000, 3'd3, h, ok);
    check("AXI OS issue size=3 reject", !ok);
    u_ahbf.bus_read_issue(32'h8200_0000, 3'd5, h, ok);
    check("AHB full OS issue size=5 reject", !ok);
    u_axi.bus_read(32'hA000_0000, 3'd0, rd, resp);
    check("AXI blocking size=0 soft", resp == `VERIF_BUS_RESP_SOFT);

    // --- V8: OS unaligned reject ---
    u_axi.bus_read_issue(32'hA000_0001, 3'd4, h, ok);
    check("AXI OS unaligned word reject", !ok);
    u_axi.bus_write_issue(32'hA000_0003, 32'h1, 3'd2, h, ok);
    check("AXI OS half@+3 reject", !ok);

    // --- V9/V10: free wait + double wait → SOFT ---
    u_apb.bus_read_wait(0, rd, resp);
    check("APB free wait SOFT", resp == `VERIF_BUS_RESP_SOFT && rd == 32'hDEADDEAD);

    u_apb.bus_write(32'h4000_0010, 32'h0000_00EE, 3'd1, resp);
    u_apb.bus_read_issue(32'h4000_0010, 3'd1, h, ok);
    check("APB OS issue for double-wait", ok);
    u_apb.bus_read_wait(h, d_wait, r_wait);
    check("APB OS first wait OK", r_wait == `VERIF_BUS_RESP_OK && d_wait[7:0] == 8'hEE);
    u_apb.bus_read_wait(h, d_wait, r_wait);
    check("APB OS double wait SOFT",
          r_wait == `VERIF_BUS_RESP_SOFT && d_wait == 32'hDEADDEAD);

    // AXI free wait
    u_axi.bus_read_wait(0, rd, resp);
    check("AXI free wait SOFT", resp == `VERIF_BUS_RESP_SOFT);

    // --- bonus: AXI OOB still SLV (sanity) ---
    u_axi.bus_read(32'hA000_2000, 3'd4, rd, resp);
    check("AXI OOB read SLV", resp == `VERIF_BUS_RESP_SLV);

    // Mid-transfer reset: see tb/tb_amba_mid_reset.v (make soc-bus-mid-reset)

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_amba_neg_paths: pass=%0d expected %0d", pass, TB_EXPECTED_PASS);
    if (fail != 0)
      $fatal(1, "tb_amba_neg_paths failed");
    $display("[SUCCESS] AMBA neg-path lock-down OK");
    $finish;
  end

endmodule
