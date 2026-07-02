// Simple APB2 slave — fixed latency, no PREADY/PSLVERR
`timescale 1ns/1ps

module verif_apb2_slave_simple #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter [31:0] BASE = 32'h4000_0000,
  parameter [31:0] SIZE = 32'h1000
)(
  input         PCLK,
  input         PRESETn,
  input  [ADDR_WIDTH-1:0] PADDR,
  input         PSEL,
  input         PENABLE,
  input         PWRITE,
  input  [DATA_WIDTH-1:0] PWDATA,
  output reg [DATA_WIDTH-1:0] PRDATA
);

  reg [7:0] mem [0:SIZE-1];
  integer i;

  initial begin
    PRDATA = 32'h0;
    for (i = 0; i < 4096; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = 8'h02;
  end

  always @(posedge PCLK) begin
    if (PSEL && PENABLE && !PWRITE &&
        PADDR >= BASE && PADDR + 4 <= BASE + SIZE)
      PRDATA <= {mem[PADDR - BASE + 3], mem[PADDR - BASE + 2],
                 mem[PADDR - BASE + 1], mem[PADDR - BASE + 0]};
    else if (PSEL && PENABLE && PWRITE &&
             PADDR >= BASE && PADDR + 4 <= BASE + SIZE) begin
      mem[PADDR - BASE + 0] <= PWDATA[7:0];
      mem[PADDR - BASE + 1] <= PWDATA[15:8];
      mem[PADDR - BASE + 2] <= PWDATA[23:16];
      mem[PADDR - BASE + 3] <= PWDATA[31:24];
    end
  end

endmodule