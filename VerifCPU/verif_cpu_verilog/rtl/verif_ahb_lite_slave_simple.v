// Simple AHB-Lite slave (behavioral) for bridge smoke tests
`timescale 1ns/1ps

module verif_ahb_lite_slave_simple #(
  parameter [31:0] BASE = 32'h8000_0000,
  parameter [31:0] SIZE = 32'h1000,
  parameter [31:0] INIT_WORD0 = 32'hDEADBEEF,
  parameter [31:0] INIT_WORD1 = 32'h00000000
)(
  input         HCLK,
  input         HRESETn,
  input  [31:0] HADDR,
  input  [2:0]  HSIZE,
  input  [1:0]  HTRANS,
  input         HWRITE,
  input  [31:0] HWDATA,
  input         HREADY,
  output reg [31:0] HRDATA,
  output reg        HREADYOUT,
  output reg [1:0]  HRESP
);

  reg [7:0] mem [0:SIZE-1];
  integer i;

  initial begin
    HRDATA = 32'h0;
    HREADYOUT = 1'b1;
    HRESP = 2'b00;
    for (i = 0; i < 4096; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = INIT_WORD0[7:0];
    mem[1] = INIT_WORD0[15:8];
    mem[2] = INIT_WORD0[23:16];
    mem[3] = INIT_WORD0[31:24];
    mem[4] = INIT_WORD1[7:0];
    mem[5] = INIT_WORD1[15:8];
    mem[6] = INIT_WORD1[23:16];
    mem[7] = INIT_WORD1[31:24];
  end

  always @(posedge HCLK) begin
    HRDATA <= 32'h0;
    HRESP <= 2'b00;
    if (HTRANS == 2'b10) begin
      if (HADDR < BASE || HADDR + 4 > BASE + SIZE)
        HRESP <= 2'b10;
      else if (HWRITE) begin
        mem[HADDR - BASE + 0] <= HWDATA[7:0];
        mem[HADDR - BASE + 1] <= HWDATA[15:8];
        mem[HADDR - BASE + 2] <= HWDATA[23:16];
        mem[HADDR - BASE + 3] <= HWDATA[31:24];
      end
      else
        HRDATA <= {mem[HADDR - BASE + 3], mem[HADDR - BASE + 2],
                   mem[HADDR - BASE + 1], mem[HADDR - BASE + 0]};
    end
  end

endmodule