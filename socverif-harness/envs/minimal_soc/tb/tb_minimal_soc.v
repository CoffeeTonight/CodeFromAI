`timescale 1ns/1ps

module tb_minimal_soc;

  reg clk = 0;
  reg rst_n = 0;
  reg bus_valid = 0;
  reg bus_wr = 0;
  reg [31:0] bus_addr = 0;
  reg [31:0] bus_wdata = 0;
  wire [31:0] bus_rdata;
  wire bus_ready;

  integer pass_count;
  integer fail_count;

  periph_soc u_dut (
    .clk(clk), .rst_n(rst_n),
    .bus_valid(bus_valid), .bus_wr(bus_wr),
    .bus_addr(bus_addr), .bus_wdata(bus_wdata),
    .bus_rdata(bus_rdata), .bus_ready(bus_ready)
  );

  always #5 clk = ~clk;

  task bus_read;
    input [31:0] addr;
    output [31:0] data;
    begin
      @(posedge clk);
      bus_valid <= 1;
      bus_wr <= 0;
      bus_addr <= addr;
      @(posedge clk);
      while (!bus_ready) @(posedge clk);
      data = bus_rdata;
      bus_valid <= 0;
      @(posedge clk);
    end
  endtask

  task bus_write;
    input [31:0] addr;
    input [31:0] data;
    begin
      @(posedge clk);
      bus_valid <= 1;
      bus_wr <= 1;
      bus_addr <= addr;
      bus_wdata <= data;
      @(posedge clk);
      while (!bus_ready) @(posedge clk);
      bus_valid <= 0;
      @(posedge clk);
    end
  endtask

  task vlp_pass;
    input [255:0] id;
    begin
      $display("VERIF PASS %s ok", id);
      pass_count = pass_count + 1;
    end
  endtask

  task vlp_fail;
    input [255:0] id;
    input [31:0] exp;
    input [31:0] got;
    begin
      $display("VERIF FAIL %s mismatch expect=0x%08x got=0x%08x", id, exp, got);
      fail_count = fail_count + 1;
    end
  endtask

  task vlp_summary;
    begin
      if (fail_count == 0 && pass_count > 0)
        $display("VERIF SUMMARY pass=%0d fail=%0d total=%0d result=PASS",
                 pass_count, fail_count, pass_count + fail_count);
      else
        $display("VERIF SUMMARY pass=%0d fail=%0d total=%0d result=FAIL",
                 pass_count, fail_count, pass_count + fail_count);
    end
  endtask

  reg [31:0] rd;

  initial begin
    pass_count = 0;
    fail_count = 0;
    rst_n = 0;
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (2) @(posedge clk);

`ifdef VERIF_TIER0
    $display("[tier0] RTL sanity — reset complete");
`elsif VERIF_TIER1
    vlp_pass("env_sanity");
    vlp_summary();
`elsif VERIF_TIER2
    bus_read(32'h4000_0000, rd);
    if (rd == 32'h0000_0001) vlp_pass("sfr_ctrl_read");
    else vlp_fail("sfr_ctrl_read", 32'h1, rd);
    bus_read(32'h8000_0000, rd);
    if (rd == 32'hDEAD_BEEF) vlp_pass("sram_marker_read");
    else vlp_fail("sram_marker_read", 32'hDEAD_BEEF, rd);
    bus_write(32'h8000_0004, 32'hA5A5_A5A5);
    bus_read(32'h8000_0004, rd);
    if (rd == 32'hA5A5_A5A5) vlp_pass("sram_aux_rw");
    else vlp_fail("sram_aux_rw", 32'hA5A5_A5A5, rd);
    vlp_summary();
`elsif VERIF_TIER3
    bus_read(32'h4000_0000, rd);
    if (rd == 32'h0000_0001) vlp_pass("sfr_ctrl_read");
    else vlp_fail("sfr_ctrl_read", 32'h1, rd);
    bus_read(32'h4000_0004, rd);
    if (rd == 32'h0000_00FF) vlp_pass("sfr_cfg_read");
    else vlp_fail("sfr_cfg_read", 32'hFF, rd);
    bus_read(32'h8000_0000, rd);
    if (rd == 32'hDEAD_BEEF) vlp_pass("sram_marker_read");
    else vlp_fail("sram_marker_read", 32'hDEAD_BEEF, rd);
    bus_write(32'h8000_0004, 32'hA5A5_A5A5);
    bus_read(32'h8000_0004, rd);
    if (rd == 32'hA5A5_A5A5) vlp_pass("sram_aux_rw");
    else vlp_fail("sram_aux_rw", 32'hA5A5_A5A5, rd);
    vlp_summary();
`else
    $display("[sanity] default");
`endif
    #20;
    $finish;
  end

  initial begin
`ifdef VERIF_TIER3
    $dumpfile("sim_logs/tier3.vcd");
    $dumpvars(1, u_dut);
`elsif VERIF_TIER2
    $dumpfile("sim_logs/tier2.vcd");
    $dumpvars(1, u_dut.bus_addr, u_dut.bus_wdata, u_dut.bus_rdata, u_dut.bus_ready);
`elsif VERIF_TIER1
    $dumpfile("sim_logs/tier1.vcd");
    $dumpvars(1, u_dut.clk, u_dut.rst_n, u_dut.bus_valid);
`else
    $dumpfile("sim_logs/tier0.vcd");
    $dumpvars(1, u_dut.clk, u_dut.rst_n);
`endif
  end

endmodule