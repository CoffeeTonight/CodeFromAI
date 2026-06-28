`timescale 1ns/1ps
module tb_toy;
  reg clk=0, rst_n=0, bus_valid=0, bus_wr=0;
  reg [31:0] bus_addr=0, bus_wdata=0;
  wire [31:0] bus_rdata; wire bus_ready;
  toy_periph u_dut(.clk(clk),.rst_n(rst_n),.bus_valid(bus_valid),.bus_wr(bus_wr),
    .bus_addr(bus_addr),.bus_wdata(bus_wdata),.bus_rdata(bus_rdata),.bus_ready(bus_ready));
  always #5 clk = ~clk;
  initial begin
    repeat(4) @(posedge clk); rst_n=1;
`ifdef VERIF_TIER0
    $display("[tier0] RTL sanity — toy boot");
`else
    $display("[toy] sanity boot");
`endif
    #20; $finish;
  end

  initial begin
    $dumpfile("sim_logs/tier0.vcd");
    $dumpvars(1, u_dut.clk, u_dut.rst_n);
  end
endmodule