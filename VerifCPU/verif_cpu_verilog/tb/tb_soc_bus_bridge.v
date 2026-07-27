// Smoke test: VerifCPU APB/AHB bridge bus_read/write tasks
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_sim_watchdog.vh"

module tb_soc_bus_bridge;

  // 14 base + 4 OS poll→wait cache contract (APB/AHB × read/write)
  localparam integer TB_EXPECTED_PASS = 18;

  `VERIF_SIM_WATCHDOG_NS

  reg apb_clk = 0;
  reg ahb_clk = 0;
  reg apb_rstn = 0;
  reg ahb_rstn = 0;
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
    .PCLK(apb_clk), .PRESETn(apb_rstn),
    .PRDATA(apb_rdata), .PREADY(apb_ready), .PSLVERR(apb_slverr),
    .PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(),
    .snoop_valid(apb_sn_v), .snoop_wr(apb_sn_wr),
    .snoop_addr(apb_sn_addr), .snoop_data(apb_sn_data)
  );

  verif_apb_slave_simple #(.BASE(32'h4000_0000)) u_apb_slv (
    .PCLK(apb_clk), .PRESETn(apb_rstn),
    .PADDR(u_apb.PADDR), .PSEL(u_apb.PSEL), .PENABLE(u_apb.PENABLE),
    .PWRITE(u_apb.PWRITE), .PWDATA(u_apb.PWDATA), .PSTRB(u_apb.PSTRB),
    .PRDATA(apb_rdata), .PREADY(apb_ready), .PSLVERR(apb_slverr)
  );

  verif_ahb_lite_master u_ahb (
    .HCLK(ahb_clk), .HRESETn(ahb_rstn),
    .HRDATA(ahb_rdata), .HREADY(ahb_readyout), .HRESP(ahb_hresp),
    .HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),
    .snoop_valid(ahb_sn_v), .snoop_wr(ahb_sn_wr),
    .snoop_addr(ahb_sn_addr), .snoop_data(ahb_sn_data)
  );

  verif_ahb_lite_slave_simple #(.BASE(32'h8000_0000)) u_ahb_slv (
    .HCLK(ahb_clk), .HRESETn(ahb_rstn),
    .HADDR(u_ahb.HADDR), .HSIZE(u_ahb.HSIZE), .HTRANS(u_ahb.HTRANS),
    .HWRITE(u_ahb.HWRITE), .HWDATA(u_ahb.HWDATA), .HREADY(1'b1),
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

    repeat (4) @(posedge apb_clk);
    apb_rstn = 1'b1;
    repeat (4) @(posedge ahb_clk);
    ahb_rstn = 1'b1;
    repeat (2) @(posedge apb_clk);
    repeat (2) @(posedge ahb_clk);

    $display("tb_soc_bus_bridge: APB + AHB bridge smoke test");

    u_apb.bus_read(32'h4000_0000, 3'd4, rd, resp);
    check("APB read SFR_CTRL", resp == 2'd0 && rd == 32'h0000_0001);

    u_ahb.bus_read(32'h8000_0000, 3'd4, rd, resp);
    check("AHB read SRAM_MARKER", resp == 2'd0 && rd == 32'hDEAD_BEEF);

    // HSIZE byte/half regression (slave must honor HSIZE, not always word)
    u_ahb.bus_write(32'h8000_0004, 32'h0000_00A5, 3'd1, resp);
    check("AHB byte write OK", resp == 2'd0);
    u_ahb.bus_read(32'h8000_0004, 3'd1, rd, resp);
    check("AHB byte read", resp == 2'd0 && rd[7:0] == 8'hA5);
    u_ahb.bus_write(32'h8000_0006, 32'h0000_BEEF, 3'd2, resp);
    check("AHB half write OK", resp == 2'd0);
    u_ahb.bus_read(32'h8000_0006, 3'd2, rd, resp);
    check("AHB half read", resp == 2'd0 && rd[15:0] == 16'hBEEF);
    // half @ byte offset 3: real two-byte split across word boundary
    u_ahb.bus_write(32'h8000_0003, 32'h0000_CDEF, 3'd2, resp);
    check("AHB half@+3 split write OK", resp == 2'd0);
    u_ahb.bus_read(32'h8000_0003, 3'd2, rd, resp);
    check("AHB half@+3 split read", resp == 2'd0 && rd[15:0] == 16'hCDEF);
    // unaligned word → 4× byte
    u_ahb.bus_write(32'h8000_0001, 32'h1122_3344, 3'd4, resp);
    check("AHB unaligned word write", resp == 2'd0);
    u_ahb.bus_read(32'h8000_0001, 3'd4, rd, resp);
    check("AHB unaligned word read", resp == 2'd0 && rd == 32'h1122_3344);

    // APB narrow + OS stub
    u_apb.bus_write(32'h4000_0008, 32'h0000_005A, 3'd1, resp);
    check("APB byte write OK", resp == 2'd0);
    u_apb.bus_read(32'h4000_0008, 3'd1, rd, resp);
    check("APB byte read", resp == 2'd0 && rd[7:0] == 8'h5A);
    begin : apb_os
      integer h;
      reg ok;
      reg [1:0] r2;
      reg [31:0] d2;
      u_apb.bus_write_issue(32'h4000_000C, 32'h0000_00C3, 3'd1, h, ok);
      check("APB OS issue", ok);
      u_apb.bus_write_wait(h, r2);
      u_apb.bus_read_issue(32'h4000_000C, 3'd1, h, ok);
      u_apb.bus_read_wait(h, d2, r2);
      check("APB OS byte r/w", r2 == 2'd0 && d2[7:0] == 8'hC3);
    end

    // OS contract: poll completes once; wait reaps cache (no re-xfer / no fake fault)
    begin : apb_os_poll_wait
      integer h;
      reg ok, done;
      reg [1:0] r_poll, r_wait;
      reg [31:0] d_poll, d_wait;
      u_apb.bus_write(32'h4000_0010, 32'h0000_00A1, 3'd1, resp);
      u_apb.bus_read_issue(32'h4000_0010, 3'd1, h, ok);
      u_apb.bus_read_poll(h, d_poll, r_poll, done);
      // Mutate after poll — wait must return cached A1, not new value
      u_apb.bus_write(32'h4000_0010, 32'h0000_00B2, 3'd1, resp);
      u_apb.bus_read_wait(h, d_wait, r_wait);
      check("APB OS poll→wait cache",
            ok && done && r_poll == 2'd0 && r_wait == 2'd0 &&
            d_poll[7:0] == 8'hA1 && d_wait[7:0] == 8'hA1);
      // Write path: poll applies once; second poll peeks; wait reaps
      u_apb.bus_write_issue(32'h4000_0014, 32'h0000_00C4, 3'd1, h, ok);
      u_apb.bus_write_poll(h, r_poll, done);
      u_apb.bus_write_poll(h, r_wait, done);  // peek, no second xfer
      u_apb.bus_write_wait(h, r_wait);
      u_apb.bus_read(32'h4000_0014, 3'd1, rd, resp);
      check("APB OS write poll→wait once",
            ok && r_wait == 2'd0 && resp == 2'd0 && rd[7:0] == 8'hC4);
    end
    begin : ahb_os_poll_wait
      integer h;
      reg ok, done;
      reg [1:0] r_poll, r_wait;
      reg [31:0] d_poll, d_wait;
      u_ahb.bus_write(32'h8000_0010, 32'h0000_00D5, 3'd1, resp);
      u_ahb.bus_read_issue(32'h8000_0010, 3'd1, h, ok);
      u_ahb.bus_read_poll(h, d_poll, r_poll, done);
      u_ahb.bus_write(32'h8000_0010, 32'h0000_00E6, 3'd1, resp);
      u_ahb.bus_read_wait(h, d_wait, r_wait);
      check("AHB OS poll→wait cache",
            ok && done && r_poll == 2'd0 && r_wait == 2'd0 &&
            d_poll[7:0] == 8'hD5 && d_wait[7:0] == 8'hD5);
      u_ahb.bus_write_issue(32'h8000_0014, 32'h0000_00F7, 3'd1, h, ok);
      u_ahb.bus_write_poll(h, r_poll, done);
      u_ahb.bus_write_wait(h, r_wait);
      u_ahb.bus_read(32'h8000_0014, 3'd1, rd, resp);
      check("AHB OS write poll→wait once",
            ok && r_wait == 2'd0 && resp == 2'd0 && rd[7:0] == 8'hF7);
    end

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_soc_bus_bridge: pass=%0d expected %0d", pass, TB_EXPECTED_PASS);
    if (fail != 0) $fatal(1, "tb_soc_bus_bridge failed");
    $display("[SUCCESS] APB/AHB bridges OK");
    $finish;
  end

endmodule