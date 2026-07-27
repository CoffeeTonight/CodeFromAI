// Simple APB3 slave (behavioral) for bridge smoke tests
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

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

  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  localparam [31:0] WORD_ALIGN_MASK = ~(STRB_WIDTH - 1);

  reg [7:0] mem [0:SIZE-1];
  integer i;
  integer bi;
  reg [31:0] acc_addr;

  initial begin
    PRDATA = {DATA_WIDTH{1'b0}};
    PREADY = 1'b1;
    PSLVERR = 1'b0;
    for (i = 0; i < SIZE; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = 8'h01;
    mem[4] = 8'hFF;
  end

  always @(posedge PCLK or negedge PRESETn) begin
    if (!PRESETn) begin
      PRDATA <= {DATA_WIDTH{1'b0}};
      PREADY <= 1'b1;
      PSLVERR <= 1'b0;
    end else begin
      PRDATA <= {DATA_WIDTH{1'b0}};
      PSLVERR <= 1'b0;
      PREADY <= 1'b1;
      if (PSEL && PENABLE) begin
        // Word-aligned window; non-wrapping span vs SIZE (no 32-bit + wrap false-accept)
        acc_addr = (PADDR - BASE) & WORD_ALIGN_MASK;
        if (PADDR < BASE ||
            !`VERIF_BUS_SPAN_OK(acc_addr, STRB_WIDTH[31:0], SIZE))
          PSLVERR <= 1'b1;
        else if (PWRITE) begin
          for (bi = 0; bi < STRB_WIDTH; bi = bi + 1)
            if (PSTRB[bi])
              mem[acc_addr + bi] <= PWDATA[bi*8 +: 8];
        end else begin
          for (bi = 0; bi < STRB_WIDTH; bi = bi + 1)
            PRDATA[bi*8 +: 8] <= mem[acc_addr + bi];
        end
      end
    end
  end

endmodule
