`timescale 1ns/1ps
module toy_periph (
  input wire clk, input wire rst_n,
  input wire bus_valid, input wire bus_wr,
  input wire [31:0] bus_addr, input wire [31:0] bus_wdata,
  output reg [31:0] bus_rdata, output reg bus_ready
);
  reg [31:0] sfr_ctrl;
  reg [31:0] sram_mem [0:15];
  initial begin sfr_ctrl = 32'h1; sram_mem[0] = 32'hCAFE_BEEF; end
  always @(posedge clk) begin
    bus_ready <= 0;
    if (bus_valid && bus_addr == 32'h4000_1000) begin
      bus_ready <= 1;
      if (bus_wr) sfr_ctrl <= bus_wdata; else bus_rdata <= sfr_ctrl;
    end else if (bus_valid && bus_addr == 32'h8000_1000) begin
      bus_ready <= 1;
      if (bus_wr) sram_mem[0] <= bus_wdata; else bus_rdata <= sram_mem[0];
    end
  end
endmodule