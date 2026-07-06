// Smoke test: all AMBA APB/AHB/AXI bridge variants (bus_read single-beat)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"

module tb_soc_bus_all;

  localparam integer ADDR_WIDTH = `VERIF_ADDR_WIDTH;
  localparam integer DATA_WIDTH = `VERIF_DATA_WIDTH;
  localparam integer AXI_ID_WIDTH = `VERIF_AXI_ID_WIDTH;

  localparam integer TB_EXPECTED_PASS = 11;
  localparam integer TB_EXPECTED_PROTOCOL_CHECKS = 24;

  reg clk = 0;
  reg rstn = 0;
  always #5 clk = ~clk;

  wire [DATA_WIDTH-1:0] apb2_rdata, apb3_rdata, apb4_rdata, apb5_rdata;
  wire        apb3_ready, apb3_slverr, apb4_ready, apb4_slverr, apb5_ready, apb5_slverr;
  wire [DATA_WIDTH-1:0] ahb_rdata, ahb5_rdata, ahbf_rdata;
  wire        ahb_ro, ahb5_ro, ahbf_ro;
  wire [1:0]  ahb_resp, ahb5_resp, ahbf_resp;
  wire        ahb_hexok, ahb5_hexok, ahbf_hexok;

  wire [DATA_WIDTH-1:0] axil_rdata, axi3_rdata, axi4_rdata, axi5_rdata;
  wire        axil_arready, axil_rvalid, axil_awready, axil_wready, axil_bvalid;
  wire [1:0]  axil_rresp, axil_bresp;
  wire        axi3_arready, axi3_rvalid, axi3_awready, axi3_wready, axi3_bvalid, axi3_rlast;
  wire [1:0]  axi3_rresp, axi3_bresp;
  wire        axi4_arready, axi4_rvalid, axi4_awready, axi4_wready, axi4_bvalid, axi4_rlast;
  wire [1:0]  axi4_rresp, axi4_bresp;
  wire        axi5_arready, axi5_rvalid, axi5_awready, axi5_wready, axi5_bvalid, axi5_rlast;
  wire [1:0]  axi5_rresp, axi5_bresp;
  wire [AXI_ID_WIDTH-1:0] axil_rid, axil_bid, axi3_rid, axi3_bid, axi4_rid, axi4_bid, axi5_rid, axi5_bid;

  wire sn_v, sn_wr;
  wire [31:0] sn_addr, sn_data;

  verif_apb2_master u_apb2 (
    .PCLK(clk), .PRESETn(rstn), .PRDATA(apb2_rdata), .PREADY(1'b1),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(),
    .snoop_valid(sn_v), .snoop_wr(sn_wr), .snoop_addr(sn_addr), .snoop_data(sn_data));
  verif_apb2_slave_simple #(.BASE(32'h4000_0000)) u_apb2_s (
    .PCLK(clk), .PRESETn(rstn), .PADDR(u_apb2.PADDR), .PSEL(u_apb2.PSEL),
    .PENABLE(u_apb2.PENABLE), .PWRITE(u_apb2.PWRITE), .PWDATA(u_apb2.PWDATA),
    .PRDATA(apb2_rdata));

  verif_apb_master u_apb3 (
    .PCLK(clk), .PRESETn(rstn), .PRDATA(apb3_rdata), .PREADY(apb3_ready), .PSLVERR(apb3_slverr),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_apb_slave_simple u_apb3_s (.PCLK(clk), .PRESETn(rstn),
    .PADDR(u_apb3.PADDR), .PSEL(u_apb3.PSEL), .PENABLE(u_apb3.PENABLE),
    .PWRITE(u_apb3.PWRITE), .PWDATA(u_apb3.PWDATA), .PSTRB(u_apb3.PSTRB),
    .PRDATA(apb3_rdata), .PREADY(apb3_ready), .PSLVERR(apb3_slverr));

  verif_apb4_master u_apb4 (
    .PCLK(clk), .PRESETn(rstn), .PRDATA(apb4_rdata), .PREADY(apb4_ready), .PSLVERR(apb4_slverr),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(), .PPROT(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_apb_slave_simple u_apb4_s (.PCLK(clk), .PRESETn(rstn),
    .PADDR(u_apb4.PADDR), .PSEL(u_apb4.PSEL), .PENABLE(u_apb4.PENABLE),
    .PWRITE(u_apb4.PWRITE), .PWDATA(u_apb4.PWDATA), .PSTRB(u_apb4.PSTRB),
    .PRDATA(apb4_rdata), .PREADY(apb4_ready), .PSLVERR(apb4_slverr));

  verif_apb5_master u_apb5 (
    .PCLK(clk), .PRESETn(rstn), .PRDATA(apb5_rdata), .PREADY(apb5_ready), .PSLVERR(apb5_slverr),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(), .PPROT(), .PWAKEUP(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_apb_slave_simple u_apb5_s (.PCLK(clk), .PRESETn(rstn),
    .PADDR(u_apb5.PADDR), .PSEL(u_apb5.PSEL), .PENABLE(u_apb5.PENABLE),
    .PWRITE(u_apb5.PWRITE), .PWDATA(u_apb5.PWDATA), .PSTRB(u_apb5.PSTRB),
    .PRDATA(apb5_rdata), .PREADY(apb5_ready), .PSLVERR(apb5_slverr));

  verif_ahb_lite_master u_ahb (
    .HCLK(clk), .HRESETn(rstn), .HRDATA(ahb_rdata), .HREADY(ahb_ro), .HRESP(ahb_resp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_ahb_lite_slave_simple u_ahb_s (.HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahb.HADDR), .HSIZE(u_ahb.HSIZE), .HTRANS(u_ahb.HTRANS),
    .HWRITE(u_ahb.HWRITE), .HWDATA(u_ahb.HWDATA), .HREADY(1'b1),
    .HRDATA(ahb_rdata), .HREADYOUT(ahb_ro), .HRESP(ahb_resp));

  assign ahb5_hexok = 1'b1;
  verif_ahb5_lite_master u_ahb5 (
    .HCLK(clk), .HRESETn(rstn), .HEXOK(ahb5_hexok),
    .HRDATA(ahb5_rdata), .HREADY(ahb5_ro), .HRESP(ahb5_resp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(), .HNONSEC(), .HEXCL(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_ahb_lite_slave_simple #(.BASE(32'h8100_0000)) u_ahb5_s (.HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahb5.HADDR), .HSIZE(u_ahb5.HSIZE), .HTRANS(u_ahb5.HTRANS),
    .HWRITE(u_ahb5.HWRITE), .HWDATA(u_ahb5.HWDATA), .HREADY(1'b1),
    .HRDATA(ahb5_rdata), .HREADYOUT(ahb5_ro), .HRESP(ahb5_resp));

  assign ahbf_hexok = 1'b1;
  verif_ahb_master u_ahbf (
    .HCLK(clk), .HRESETn(rstn), .HEXOK(ahbf_hexok),
    .HRDATA(ahbf_rdata), .HREADY(ahbf_ro), .HRESP(ahbf_resp),
    .HADDR(), .HSIZE(), .HTRANS(), .HBURST(), .HPROT(), .HMASTLOCK(),
    .HWRITE(), .HWDATA(), .HNONSEC(), .HEXCL(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_ahb_lite_slave_simple #(.BASE(32'h8200_0000)) u_ahbf_s (.HCLK(clk), .HRESETn(rstn),
    .HADDR(u_ahbf.HADDR), .HSIZE(u_ahbf.HSIZE), .HTRANS(u_ahbf.HTRANS),
    .HWRITE(u_ahbf.HWRITE), .HWDATA(u_ahbf.HWDATA), .HREADY(1'b1),
    .HRDATA(ahbf_rdata), .HREADYOUT(ahbf_ro), .HRESP(ahbf_resp));

  verif_axi_lite_master u_axil (
    .ACLK(clk), .ARESETn(rstn),
    .ARREADY(axil_arready), .RVALID(axil_rvalid), .RDATA(axil_rdata), .RRESP(axil_rresp),
    .AWREADY(axil_awready), .WREADY(axil_wready), .BVALID(axil_bvalid), .BRESP(axil_bresp),
    .ARVALID(), .ARADDR(), .ARSIZE(), .RREADY(), .AWVALID(), .AWADDR(), .AWSIZE(),
    .WVALID(), .WDATA(), .WSTRB(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_axi_full_slave_simple #(.BASE(32'hC000_0000)) u_axil_s (.ACLK(clk), .ARESETn(rstn),
    .ARID({AXI_ID_WIDTH{1'b0}}), .ARADDR(u_axil.ARADDR), .ARLEN(8'd0), .ARSIZE(u_axil.ARSIZE),
    .ARBURST(2'b01), .ARVALID(u_axil.ARVALID), .ARREADY(axil_arready),
    .RID(axil_rid), .RDATA(axil_rdata), .RRESP(axil_rresp), .RLAST(axil_rvalid), .RVALID(axil_rvalid), .RREADY(u_axil.RREADY),
    .AWID({AXI_ID_WIDTH{1'b0}}), .AWADDR(u_axil.AWADDR), .AWLEN(8'd0), .AWSIZE(u_axil.AWSIZE),
    .AWBURST(2'b01), .AWVALID(u_axil.AWVALID), .AWREADY(axil_awready),
    .WID({AXI_ID_WIDTH{1'b0}}), .WDATA(u_axil.WDATA), .WSTRB(u_axil.WSTRB), .WLAST(1'b1), .WVALID(u_axil.WVALID), .WREADY(axil_wready),
    .BID(axil_bid), .BRESP(axil_bresp), .BVALID(axil_bvalid), .BREADY(u_axil.BREADY));

  verif_axi_full_master #(.AXI_PROT(3)) u_axi3 (
    .ACLK(clk), .ARESETn(rstn),
    .ARREADY(axi3_arready), .RVALID(axi3_rvalid), .RDATA(axi3_rdata), .RRESP(axi3_rresp), .RLAST(axi3_rlast),
    .AWREADY(axi3_awready), .WREADY(axi3_wready), .BVALID(axi3_bvalid), .BRESP(axi3_bresp),
    .RID({AXI_ID_WIDTH{1'b0}}), .BID({AXI_ID_WIDTH{1'b0}}),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_axi_full_slave_simple #(.BASE(32'hA000_0000)) u_axi3_s (.ACLK(clk), .ARESETn(rstn),
    .ARID(u_axi3.ARID), .ARADDR(u_axi3.ARADDR), .ARLEN(u_axi3.ARLEN), .ARSIZE(u_axi3.ARSIZE),
    .ARBURST(u_axi3.ARBURST), .ARVALID(u_axi3.ARVALID), .ARREADY(axi3_arready),
    .RID(axi3_rid), .RDATA(axi3_rdata), .RRESP(axi3_rresp), .RLAST(axi3_rlast), .RVALID(axi3_rvalid), .RREADY(u_axi3.RREADY),
    .AWID(u_axi3.AWID), .AWADDR(u_axi3.AWADDR), .AWLEN(u_axi3.AWLEN), .AWSIZE(u_axi3.AWSIZE),
    .AWBURST(u_axi3.AWBURST), .AWVALID(u_axi3.AWVALID), .AWREADY(axi3_awready),
    .WID(u_axi3.WID), .WDATA(u_axi3.WDATA), .WSTRB(u_axi3.WSTRB), .WLAST(u_axi3.WLAST), .WVALID(u_axi3.WVALID), .WREADY(axi3_wready),
    .BID(axi3_bid), .BRESP(axi3_bresp), .BVALID(axi3_bvalid), .BREADY(u_axi3.BREADY));

  verif_axi_full_master #(.AXI_PROT(4)) u_axi4 (
    .ACLK(clk), .ARESETn(rstn),
    .ARREADY(axi4_arready), .RVALID(axi4_rvalid), .RDATA(axi4_rdata), .RRESP(axi4_rresp), .RLAST(axi4_rlast),
    .AWREADY(axi4_awready), .WREADY(axi4_wready), .BVALID(axi4_bvalid), .BRESP(axi4_bresp),
    .RID({AXI_ID_WIDTH{1'b0}}), .BID({AXI_ID_WIDTH{1'b0}}),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_axi_full_slave_simple #(.BASE(32'hA100_0000)) u_axi4_s (.ACLK(clk), .ARESETn(rstn),
    .ARID(u_axi4.ARID), .ARADDR(u_axi4.ARADDR), .ARLEN(u_axi4.ARLEN), .ARSIZE(u_axi4.ARSIZE),
    .ARBURST(u_axi4.ARBURST), .ARVALID(u_axi4.ARVALID), .ARREADY(axi4_arready),
    .RID(axi4_rid), .RDATA(axi4_rdata), .RRESP(axi4_rresp), .RLAST(axi4_rlast), .RVALID(axi4_rvalid), .RREADY(u_axi4.RREADY),
    .AWID(u_axi4.AWID), .AWADDR(u_axi4.AWADDR), .AWLEN(u_axi4.AWLEN), .AWSIZE(u_axi4.AWSIZE),
    .AWBURST(u_axi4.AWBURST), .AWVALID(u_axi4.AWVALID), .AWREADY(axi4_awready),
    .WID({AXI_ID_WIDTH{1'b0}}), .WDATA(u_axi4.WDATA), .WSTRB(u_axi4.WSTRB), .WLAST(u_axi4.WLAST), .WVALID(u_axi4.WVALID), .WREADY(axi4_wready),
    .BID(axi4_bid), .BRESP(axi4_bresp), .BVALID(axi4_bvalid), .BREADY(u_axi4.BREADY));

  verif_axi_full_master #(.AXI_PROT(5)) u_axi5 (
    .ACLK(clk), .ARESETn(rstn),
    .ARREADY(axi5_arready), .RVALID(axi5_rvalid), .RDATA(axi5_rdata), .RRESP(axi5_rresp), .RLAST(axi5_rlast),
    .AWREADY(axi5_awready), .WREADY(axi5_wready), .BVALID(axi5_bvalid), .BRESP(axi5_bresp),
    .RID({AXI_ID_WIDTH{1'b0}}), .BID({AXI_ID_WIDTH{1'b0}}),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data());
  verif_axi_full_slave_simple #(.BASE(32'hA200_0000)) u_axi5_s (.ACLK(clk), .ARESETn(rstn),
    .ARID(u_axi5.ARID), .ARADDR(u_axi5.ARADDR), .ARLEN(u_axi5.ARLEN), .ARSIZE(u_axi5.ARSIZE),
    .ARBURST(u_axi5.ARBURST), .ARVALID(u_axi5.ARVALID), .ARREADY(axi5_arready),
    .RID(axi5_rid), .RDATA(axi5_rdata), .RRESP(axi5_rresp), .RLAST(axi5_rlast), .RVALID(axi5_rvalid), .RREADY(u_axi5.RREADY),
    .AWID(u_axi5.AWID), .AWADDR(u_axi5.AWADDR), .AWLEN(u_axi5.AWLEN), .AWSIZE(u_axi5.AWSIZE),
    .AWBURST(u_axi5.AWBURST), .AWVALID(u_axi5.AWVALID), .AWREADY(axi5_awready),
    .WID({AXI_ID_WIDTH{1'b0}}), .WDATA(u_axi5.WDATA), .WSTRB(u_axi5.WSTRB), .WLAST(u_axi5.WLAST), .WVALID(u_axi5.WVALID), .WREADY(axi5_wready),
    .BID(axi5_bid), .BRESP(axi5_bresp), .BVALID(axi5_bvalid), .BREADY(u_axi5.BREADY));

  reg [31:0] rd;
  reg [1:0]  resp;
  integer pass, fail;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    $dumpfile("sim_build/tb_soc_bus_all.vcd");
    $dumpvars(0, tb_soc_bus_all);
    pass = 0; fail = 0;
    repeat (4) @(posedge clk);
    rstn = 1'b1;
    repeat (2) @(posedge clk);
    $display("tb_soc_bus_all: AMBA APB/AHB/AXI bridge smoke");

    u_apb2.bus_read(32'h4000_0000, 3'd4, rd, resp);
    check("APB2", resp == 0 && rd == 32'h0000_0002);
    u_apb3.bus_read(32'h4000_0000, 3'd4, rd, resp);
    check("APB3", resp == 0 && rd == 32'h0000_0001);
    u_apb4.bus_read(32'h4000_0000, 3'd4, rd, resp);
    check("APB4", resp == 0 && rd == 32'h0000_0001);
    u_apb5.bus_read(32'h4000_0000, 3'd4, rd, resp);
    check("APB5", resp == 0 && rd == 32'h0000_0001);

    u_ahb.bus_read(32'h8000_0000, 3'd4, rd, resp);
    check("AHB-Lite", resp == 0 && rd == 32'hDEAD_BEEF);
    u_ahb5.bus_read(32'h8100_0000, 3'd4, rd, resp);
    check("AHB5-Lite", resp == 0 && rd == 32'hDEAD_BEEF);
    u_ahbf.bus_read(32'h8200_0000, 3'd4, rd, resp);
    check("AHB full", resp == 0 && rd == 32'hDEAD_BEEF);

    u_axil.bus_read(32'hC000_0000, 3'd4, rd, resp);
    check("AXI4-Lite", resp == 0 && rd == 32'h0000_00A3);
    u_axi3.bus_read(32'hA000_0000, 3'd4, rd, resp);
    check("AXI3 full", resp == 0 && rd == 32'h0000_00A3);
    u_axi4.bus_read(32'hA100_0000, 3'd4, rd, resp);
    check("AXI4 full", resp == 0 && rd == 32'h0000_00A3);
    u_axi5.bus_read(32'hA200_0000, 3'd4, rd, resp);
    check("AXI5 full", resp == 0 && rd == 32'h0000_00A3);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "tb_soc_bus_all failed");
    $display("[SUCCESS] All AMBA bridge variants OK");
    $finish;
  end

endmodule