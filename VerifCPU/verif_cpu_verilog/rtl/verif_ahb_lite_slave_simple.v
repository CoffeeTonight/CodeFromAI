// Simple AHB-Lite slave (behavioral) for bridge smoke tests
`timescale 1ns/1ps
`include "verif_bus_lane_helpers.vh"

module verif_ahb_lite_slave_simple #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter [31:0] BASE = 32'h8000_0000,
  parameter [31:0] SIZE = 32'h1000,
  parameter [31:0] INIT_WORD0 = 32'hDEADBEEF,
  parameter [31:0] INIT_WORD1 = 32'h00000000
)(
  input         HCLK,
  input         HRESETn,
  input  [ADDR_WIDTH-1:0] HADDR,
  input  [2:0]  HSIZE,
  input  [1:0]  HTRANS,
  input         HWRITE,
  input  [DATA_WIDTH-1:0] HWDATA,
  input         HREADY,
  output reg [DATA_WIDTH-1:0] HRDATA,
  output reg        HREADYOUT,
  output reg [1:0]  HRESP
);

  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)

  reg [7:0] mem [0:SIZE-1];
  integer i;
  reg [STRB_WIDTH-1:0] wstrb;
  integer bi;
  reg [2:0] acc_sz;
  reg [31:0] acc_addr;

  function [2:0] hsize_to_acc;
    input [2:0] hsize;
    begin
      case (hsize)
        3'd0: hsize_to_acc = 3'd1;
        3'd1: hsize_to_acc = 3'd2;
        default: hsize_to_acc = 3'd4;
      endcase
    end
  endfunction

  function [31:0] access_span_end;
    input [31:0] addr;
    input [2:0]  size;
    reg [31:0] span;
    begin
      case (size)
        3'd1: span = 32'd1;
        3'd2: span = 32'd2;
        default: span = 32'd4;
      endcase
      access_span_end = addr + span;
    end
  endfunction

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
    HRESP <= 2'b00;
    if (HTRANS == 2'b10) begin
      acc_sz = hsize_to_acc(HSIZE);
      acc_addr = HADDR;
      if (HADDR < BASE || access_span_end(HADDR, acc_sz) > BASE + SIZE)
        HRESP <= 2'b10;
      else if (HWRITE) begin
        acc_addr = (HADDR - BASE) & 32'hFFFFFFFC;
        wstrb = lane_wstrb(HADDR, acc_sz);
        for (bi = 0; bi < STRB_WIDTH; bi = bi + 1)
          if (wstrb[bi])
            mem[acc_addr + bi] <= HWDATA[bi*8 +: 8];
      end
      else begin
        acc_addr = (HADDR - BASE) & 32'hFFFFFFFC;
        HRDATA <= {mem[acc_addr + 3], mem[acc_addr + 2],
                   mem[acc_addr + 1], mem[acc_addr + 0]};
      end
    end
  end

endmodule