// Simple APB3 slave (behavioral) for bridge smoke tests
`timescale 1ns/1ps

module verif_apb_slave_simple #(
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
  input  [DATA_WIDTH/8-1:0] PSTRB,
  output reg [DATA_WIDTH-1:0] PRDATA,
  output reg        PREADY,
  output reg        PSLVERR
);

  reg [7:0] mem [0:SIZE-1];
  integer i;

  initial begin
    PRDATA = 32'h0;
    PREADY = 1'b1;
    PSLVERR = 1'b0;
    for (i = 0; i < 4096; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = 8'h01;
    mem[4] = 8'hFF;
  end

  always @(posedge PCLK) begin
    PRDATA <= 32'h0;
    PSLVERR <= 1'b0;
    if (PSEL && PENABLE) begin
      if (PADDR < BASE || PADDR + 4 > BASE + SIZE)
        PSLVERR <= 1'b1;
      else if (PWRITE) begin
        if (PSTRB[0]) mem[PADDR - BASE + 0] <= PWDATA[7:0];
        if (PSTRB[1]) mem[PADDR - BASE + 1] <= PWDATA[15:8];
        if (PSTRB[2]) mem[PADDR - BASE + 2] <= PWDATA[23:16];
        if (PSTRB[3]) mem[PADDR - BASE + 3] <= PWDATA[31:24];
      end else begin
        PRDATA <= {mem[PADDR - BASE + 3], mem[PADDR - BASE + 2],
                   mem[PADDR - BASE + 1], mem[PADDR - BASE + 0]};
      end
    end
  end

endmodule