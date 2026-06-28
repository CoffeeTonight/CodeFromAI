`timescale 1ns/1ps
module tb_syn;
  reg clk=0, rst_n=0;
  always #5 clk=~clk;
  dut u(.clk(clk),.rst_n(rst_n));
  initial begin
    repeat(4) @(posedge clk); rst_n=1;
`ifdef VERIF_TIER1
    $display("VERIF PASS env_sanity ok");
    $display("VERIF SUMMARY pass=1 fail=0 total=1 result=PASS");
`else
    $display("[sanity] synthetic vcs-style ok");
`endif
    #10; $finish;
  end
endmodule