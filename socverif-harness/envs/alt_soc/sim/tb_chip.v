`timescale 1ns/1ps

module tb_chip;

  reg clk=0, rst_n=0, req=0, wen=0;
  reg [31:0] addr=0, wdata=0;
  wire [31:0] rdata;
  wire ack;
  integer pass_count, fail_count;

  chip_mem u_mem (.clk(clk), .rst_n(rst_n), .req(req), .wen(wen),
                  .addr(addr), .wdata(wdata), .rdata(rdata), .ack(ack));
  always #5 clk = ~clk;

  task mem_read; input [31:0] a; output [31:0] d;
    begin @(posedge clk); req<=1; wen<=0; addr<=a; @(posedge clk);
      while(!ack) @(posedge clk); d=rdata; req<=0; @(posedge clk); end endtask
  task mem_write; input [31:0] a,d;
    begin @(posedge clk); req<=1; wen<=1; addr<=a; wdata<=d; @(posedge clk);
      while(!ack) @(posedge clk); req<=0; @(posedge clk); end endtask
  task vlp_pass; input [255:0] id; begin $display("VERIF PASS %s ok",id); pass_count++; end endtask
  task vlp_fail; input [255:0] id; input [31:0] e,g;
    begin $display("VERIF FAIL %s mismatch expect=0x%08x got=0x%08x",id,e,g); fail_count++; end endtask
  task vlp_summary;
    begin if(fail_count==0&&pass_count>0)
      $display("VERIF SUMMARY pass=%0d fail=%0d total=%0d result=PASS",pass_count,fail_count,pass_count+fail_count);
    else $display("VERIF SUMMARY pass=%0d fail=%0d total=%0d result=FAIL",pass_count,fail_count,pass_count+fail_count);
    end endtask

  reg [31:0] rd;
  initial begin
    pass_count=0; fail_count=0; rst_n=0; repeat(4) @(posedge clk); rst_n=1; repeat(2) @(posedge clk);
`ifdef VERIF_TIER1
    vlp_pass("env_sanity"); vlp_summary();
`elsif VERIF_TIER2
    mem_read(32'h5000_0000, rd);
    if(rd==32'hAB) vlp_pass("reg_sys_ctrl_read"); else vlp_fail("reg_sys_ctrl_read",32'hAB,rd);
    mem_read(32'h6000_0000, rd);
    if(rd==32'h12345678) vlp_pass("mem_test0_read"); else vlp_fail("mem_test0_read",32'h12345678,rd);
    mem_write(32'h6000_0004, 32'hA5A5A5A5); mem_read(32'h6000_0004, rd);
    if(rd==32'hA5A5A5A5) vlp_pass("mem_test1_rw"); else vlp_fail("mem_test1_rw",32'hA5A5A5A5,rd);
    vlp_summary();
`elsif VERIF_TIER3
    mem_read(32'h5000_0000, rd);
    if(rd==32'hAB) vlp_pass("reg_sys_ctrl_read"); else vlp_fail("reg_sys_ctrl_read",32'hAB,rd);
    mem_read(32'h5000_0004, rd);
    if(rd==32'h55) vlp_pass("reg_sys_cfg_read"); else vlp_fail("reg_sys_cfg_read",32'h55,rd);
    mem_read(32'h6000_0000, rd);
    if(rd==32'h12345678) vlp_pass("mem_test0_read"); else vlp_fail("mem_test0_read",32'h12345678,rd);
    mem_write(32'h6000_0004, 32'hA5A5A5A5); mem_read(32'h6000_0004, rd);
    if(rd==32'hA5A5A5A5) vlp_pass("mem_test1_rw"); else vlp_fail("mem_test1_rw",32'hA5A5A5A5,rd);
    vlp_summary();
`else
    $display("[alt_soc tier0] compile and sim ok");
`endif
    #20; $finish;
  end

  initial begin
`ifdef VERIF_TIER2
    $dumpfile("../logs/tier2.vcd");
    $dumpvars(1, u_mem.addr, u_mem.wdata, u_mem.rdata, u_mem.ack);
`elsif VERIF_TIER1
    $dumpfile("../logs/tier1.vcd");
    $dumpvars(1, u_mem.clk, u_mem.req, u_mem.ack);
`else
    $dumpfile("../logs/tier0.vcd");
    $dumpvars(1, u_mem.clk, u_mem.rst_n);
`endif
  end
endmodule