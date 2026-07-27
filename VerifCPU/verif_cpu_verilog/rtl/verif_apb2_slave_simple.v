// Simple APB2 slave — no PREADY/PSLVERR/PSTRB
// Writes merge into word-aligned mem using lane_wstrb from access size.
// Size is not on the wire: master must RMW for narrow stores (apb2 master does).
// This slave treats every write as a full-word PWDATA overlay with strb=all-ones
// only when PADDR is word-aligned; for unaligned PADDR writes a single byte.
// Prefer: master always presents full-word PWDATA after RMW (see verif_apb2_master).
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
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
  integer bi;
  reg [STRB_WIDTH-1:0] wstrb;
  reg [31:0] a_rel;
  reg [2:0]  wr_sz;

  initial begin
    PRDATA = 32'h0;
    for (i = 0; i < SIZE; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = 8'h02;
  end

  always @(posedge PCLK or negedge PRESETn) begin
    if (!PRESETn) begin
      PRDATA <= 32'h0;
    end else if (PSEL && PENABLE && PADDR >= BASE) begin
      a_rel = (PADDR - BASE) & 32'hFFFFFFFC;
      // Non-wrapping 4-byte word window in mem[] (no +4 wrap false-accept)
      if (`VERIF_BUS_SPAN_OK(a_rel, 32'd4, SIZE)) begin
        if (!PWRITE) begin
          PRDATA <= {mem[a_rel + 3], mem[a_rel + 2],
                     mem[a_rel + 1], mem[a_rel + 0]};
        end else begin
          // Master RMW for narrow: full-word PWDATA on aligned; unaligned = byte
          if (PADDR[1:0] == 2'b00)
            wr_sz = 3'd4;
          else
            wr_sz = 3'd1;
          wstrb = lane_wstrb(PADDR, wr_sz);
          for (bi = 0; bi < STRB_WIDTH; bi = bi + 1)
            if (wstrb[bi])
              mem[a_rel + bi] <= PWDATA[bi*8 +: 8];
        end
      end
    end
  end

endmodule
