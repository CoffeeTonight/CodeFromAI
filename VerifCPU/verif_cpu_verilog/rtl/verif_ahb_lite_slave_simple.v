// Simple AHB-Lite slave (behavioral) — address/data pipeline + 2-cycle ERROR
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"
`include "verif_bus_size_helpers.vh"

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
  `VERIF_BUS_SIZE_FUNCS

  localparam HTRANS_IDLE   = 2'b00;
  localparam HTRANS_BUSY   = 2'b01;
  localparam HTRANS_NONSEQ = 2'b10;
  localparam HTRANS_SEQ    = 2'b11;
  localparam HRESP_OKAY    = 2'b00;
  localparam HRESP_ERROR   = 2'b01;

  reg [7:0] mem [0:SIZE-1];
  integer i;
  integer bi;
  reg [STRB_WIDTH-1:0] wstrb;

  // Pipelined address phase → data phase
  reg        dphase_active;
  reg        dphase_write;
  reg        dphase_error;
  reg [31:0] dphase_addr;
  reg [2:0]  dphase_size;
  reg        err_hold;  // second cycle of 2-cycle ERROR

  function [2:0] hsize_to_acc;
    input [2:0] hsize;
    begin
      hsize_to_acc = bus_hsize_to_bytes(hsize);
    end
  endfunction

  function [31:0] access_byte_count;
    input [2:0] size;
    begin
      case (size)
        3'd1: access_byte_count = 32'd1;
        3'd2: access_byte_count = 32'd2;
        3'd4: access_byte_count = 32'd4;
        default: access_byte_count = 32'd0;  // illegal
      endcase
    end
  endfunction

  // Non-wrapping: access bytes + word-aligned mem window both fit (slave r/w is word)
  function integer addr_ok;
    input [31:0] addr;
    input [2:0]  size;
    reg [31:0] nbytes;
    reg [31:0] a_rel;
    begin
      nbytes = access_byte_count(size);
      if (!`VERIF_BUS_REL_SPAN_OK(addr, nbytes, BASE, SIZE))
        addr_ok = 0;
      else begin
        a_rel = (addr - BASE) & 32'hFFFFFFFC;
        addr_ok = `VERIF_BUS_SPAN_OK(a_rel, 32'd4, SIZE) ? 1 : 0;
      end
    end
  endfunction

  initial begin
    HRDATA = 32'h0;
    HREADYOUT = 1'b1;
    HRESP = HRESP_OKAY;
    dphase_active = 1'b0;
    dphase_write = 1'b0;
    dphase_error = 1'b0;
    dphase_addr = 32'h0;
    dphase_size = 3'd4;
    err_hold = 1'b0;
    for (i = 0; i < SIZE; i = i + 1)
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

  always @(posedge HCLK or negedge HRESETn) begin
    reg [2:0]  sz;
    reg [31:0] a_rel;
    if (!HRESETn) begin
      HRDATA <= 32'h0;
      HREADYOUT <= 1'b1;
      HRESP <= HRESP_OKAY;
      dphase_active <= 1'b0;
      dphase_write <= 1'b0;
      dphase_error <= 1'b0;
      err_hold <= 1'b0;
    end else begin
      // AMBA 2-cycle ERROR: cycle1 HREADYOUT=0+HRESP=ERROR, cycle2 HREADYOUT=1+HRESP=ERROR
      if (err_hold) begin
        HRESP <= HRESP_ERROR;
        HREADYOUT <= 1'b1;
        err_hold <= 1'b0;
        dphase_active <= 1'b0;
        dphase_error <= 1'b0;
      end else if (dphase_active) begin
        if (dphase_error) begin
          // Should not normally hit: error accept already set err_hold
          HRESP <= HRESP_ERROR;
          HREADYOUT <= 1'b0;
          err_hold <= 1'b1;
        end else begin
          HRESP <= HRESP_OKAY;
          HREADYOUT <= 1'b1;
          a_rel = (dphase_addr - BASE) & 32'hFFFFFFFC;
          if (dphase_write) begin
            wstrb = lane_wstrb(dphase_addr, dphase_size);
            for (bi = 0; bi < STRB_WIDTH; bi = bi + 1)
              if (wstrb[bi])
                mem[a_rel + bi] <= HWDATA[bi*8 +: 8];
          end
          dphase_active <= 1'b0;
        end
      end else begin
        HRESP <= HRESP_OKAY;
        HREADYOUT <= 1'b1;
      end

      // Accept when HREADY. Block while ERROR cycle-1 (err_hold pending after accept).
      if (!err_hold && !(dphase_active && dphase_error) && HREADY &&
          (HTRANS == HTRANS_NONSEQ || HTRANS == HTRANS_SEQ)) begin
        sz = hsize_to_acc(HSIZE);
        dphase_addr <= HADDR;
        dphase_size <= sz;
        dphase_write <= HWRITE;
        if (!addr_ok(HADDR, sz)) begin
          // ERROR c1 this edge: not-ready + ERROR; next edge err_hold = ERROR c2 ready
          dphase_error <= 1'b1;
          dphase_active <= 1'b1;
          HRESP <= HRESP_ERROR;
          HREADYOUT <= 1'b0;
          err_hold <= 1'b1;
        end else begin
          dphase_error <= 1'b0;
          dphase_active <= 1'b1;
          if (!HWRITE) begin
            a_rel = (HADDR - BASE) & 32'hFFFFFFFC;
            HRDATA <= {mem[a_rel + 3], mem[a_rel + 2],
                       mem[a_rel + 1], mem[a_rel + 0]};
          end
        end
      end
    end
  end

endmodule
