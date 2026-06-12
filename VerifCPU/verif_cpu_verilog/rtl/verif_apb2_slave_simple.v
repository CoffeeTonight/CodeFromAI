// Simple APB2 slave — fixed latency, no PREADY/PSLVERR
`timescale 1ns/1ps

module verif_apb2_slave_simple #(
  parameter [31:0] BASE = 32'h4000_0000,
  parameter [31:0] SIZE = 32'h1000
)(
  input         PCLK,
  input         PRESETn,
  input  [31:0] PADDR,
  input         PSEL,
  input         PENABLE,
  input         PWRITE,
  input  [31:0] PWDATA,
  output reg [31:0] PRDATA
);

  reg [7:0] mem [0:4095];
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
             PADDR >= BASE && PADDR + 4 <= BASE + SIZE)
      mem[PADDR - BASE] <= PWDATA[7:0];
  end

endmodule