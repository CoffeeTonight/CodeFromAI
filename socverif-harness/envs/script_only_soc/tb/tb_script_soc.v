`timescale 1ns/1ps

module tb_script_soc;

  reg clk = 0;
  reg rst_n = 0;
  reg bus_valid = 0;
  reg bus_wr = 0;
  reg [31:0] bus_addr = 0;
  reg [31:0] bus_wdata = 0;
  wire [31:0] bus_rdata;
  wire bus_ready;

  periph_soc u_dut (
    .clk(clk), .rst_n(rst_n),
    .bus_valid(bus_valid), .bus_wr(bus_wr),
    .bus_addr(bus_addr), .bus_wdata(bus_wdata),
    .bus_rdata(bus_rdata), .bus_ready(bus_ready)
  );

  always #5 clk = ~clk;

  initial begin
    rst_n = 0;
    repeat (4) @(posedge clk);
    rst_n = 1;
    repeat (2) @(posedge clk);
    $display("[script_soc] RTL sanity — reset complete");
    #20;
    $finish;
  end

endmodule