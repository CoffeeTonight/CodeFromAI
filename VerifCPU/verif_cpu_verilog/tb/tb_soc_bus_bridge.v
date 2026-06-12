// Smoke test: VerifCPU APB/AHB bridge bus_read/write tasks
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module tb_soc_bus_bridge;

  reg apb_clk = 0;
  reg ahb_clk = 0;
  always #5 apb_clk = ~apb_clk;
  always #5 ahb_clk = ~ahb_clk;

  wire [31:0] apb_rdata;
  wire        apb_ready;
  wire        apb_slverr;

  wire [31:0] ahb_rdata;
  wire        ahb_readyout;
  wire [1:0]  ahb_hresp;

  wire        apb_sn_v, apb_sn_wr, ahb_sn_v, ahb_sn_wr;
  wire [31:0] apb_sn_addr, apb_sn_data, ahb_sn_addr, ahb_sn_data;

  verif_apb_master u_apb (
    .PCLK(apb_clk), .PRESETn(1'b1),
    .PRDATA(apb_rdata), .PREADY(apb_ready), .PSLVERR(apb_slverr),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(),
    .snoop_valid(apb_sn_v), .snoop_wr(apb_sn_wr),
    .snoop_addr(apb_sn_addr), .snoop_data(apb_sn_data)
  );

  verif_apb_slave_simple #(.BASE(32'h4000_0000)) u_apb_slv (
    .PCLK(apb_clk), .PRESETn(1'b1),
    .PADDR(u_apb.PADDR), .PSEL(u_apb.PSEL), .PENABLE(u_apb.PENABLE),
    .PWRITE(u_apb.PWRITE), .PWDATA(u_apb.PWDATA), .PSTRB(u_apb.PSTRB),
    .PRDATA(apb_rdata), .PREADY(apb_ready), .PSLVERR(apb_slverr)
  );

  verif_ahb_lite_master u_ahb (
    .HCLK(ahb_clk), .HRESETn(1'b1),
    .HRDATA(ahb_rdata), .HREADYOUT(ahb_readyout), .HRESP(ahb_hresp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(), .HREADY(),
    .snoop_valid(ahb_sn_v), .snoop_wr(ahb_sn_wr),
    .snoop_addr(ahb_sn_addr), .snoop_data(ahb_sn_data)
  );

  verif_ahb_lite_slave_simple #(.BASE(32'h8000_0000)) u_ahb_slv (
    .HCLK(ahb_clk), .HRESETn(1'b1),
    .HADDR(u_ahb.HADDR), .HSIZE(u_ahb.HSIZE), .HTRANS(u_ahb.HTRANS),
    .HWRITE(u_ahb.HWRITE), .HWDATA(u_ahb.HWDATA), .HREADY(u_ahb.HREADY),
    .HRDATA(ahb_rdata), .HREADYOUT(ahb_readyout), .HRESP(ahb_hresp)
  );

  reg [31:0] rd;
  reg [1:0]  resp;
  integer pass, fail;

  task check;
    input [8*64:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    $dumpfile("sim_build/tb_soc_bus_bridge.vcd");
    $dumpvars(0, tb_soc_bus_bridge);

    $display("tb_soc_bus_bridge: APB + AHB bridge smoke test");

    u_apb.bus_read(32'h4000_0000, 3'd4, rd, resp);
    check("APB read SFR_CTRL", resp == 2'd0 && rd == 32'h0000_0001);

    u_ahb.bus_read(32'h8000_0000, 3'd4, rd, resp);
    check("AHB read SRAM_MARKER", resp == 2'd0 && rd == 32'hDEAD_BEEF);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "tb_soc_bus_bridge failed");
    $display("[SUCCESS] APB/AHB bridges OK");
    $finish;
  end

endmodule