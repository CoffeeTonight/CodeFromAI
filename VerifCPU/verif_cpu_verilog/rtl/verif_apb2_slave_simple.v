// Simple APB2 slave — fixed latency, no PREADY/PSLVERR/PSTRB
`timescale 1ns/1ps
`include "verif_bus_lane_helpers.vh"

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

  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)

  reg [7:0] mem [0:SIZE-1];
  integer i;
  reg [STRB_WIDTH-1:0] wstrb;
  integer bi;

  function [2:0] infer_write_size;
    input [31:0] addr;
    input [31:0] wdata;
    begin
      if (addr[1:0] != 2'b00)
        infer_write_size = 3'd1;
      else if (wdata[31:16] != 0)
        infer_write_size = 3'd4;
      else if (wdata[15:8] != 0)
        infer_write_size = 3'd2;
      else
        infer_write_size = 3'd1;
    end
  endfunction

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
      wstrb = lane_wstrb(PADDR, infer_write_size(PADDR, PWDATA));
      for (bi = 0; bi < STRB_WIDTH; bi = bi + 1)
        if (wstrb[bi])
          mem[PADDR - BASE + bi] <= PWDATA[bi*8 +: 8];
    end
  end

endmodule