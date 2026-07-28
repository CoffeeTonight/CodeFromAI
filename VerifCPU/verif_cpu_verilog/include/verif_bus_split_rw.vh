// Split misaligned accesses into legal single-beat AMBA transfers:
//  - half (size=2) at addr[1:0]==3  → 2× byte
//  - word (size=4) at addr[1:0]!=0 → 4× byte
// Preserve worst resp among beats (DEC=3 > SLV=2 > SOFT=1 > OK=0).
// On SLV/DEC stop further beats (no partial multi-store after real bus fault).
// Include after PRIM_READ / PRIM_WRITE exist; verif_bus_defs.vh for RESP codes.
// Usage: `VERIF_BUS_DEFINE_SPLIT_RW(ahb_read, ahb_write)
`ifndef VERIF_BUS_SPLIT_RW_VH
`define VERIF_BUS_SPLIT_RW_VH

`define VERIF_BUS_RESP_WORSE(A, B) \
  (((A) == 2'd3 || (B) == 2'd3) ? 2'd3 : \
   ((A) == 2'd2 || (B) == 2'd2) ? 2'd2 : \
   ((A) == 2'd1 || (B) == 2'd1) ? 2'd1 : 2'd0)

`define VERIF_BUS_RESP_IS_HARD(R) \
  (((R) == `VERIF_BUS_RESP_SLV) || ((R) == `VERIF_BUS_RESP_DEC))

`define VERIF_BUS_DEFINE_SPLIT_RW(PRIM_READ, PRIM_WRITE) \
  task bus_read; \
    input  [31:0] addr; \
    input  [2:0]  size; \
    output [31:0] data; \
    output [1:0]  resp; \
    reg [31:0] d0, d1, d2, d3; \
    reg [1:0]  r0, r1, r2, r3; \
    begin \
      data = 32'h0; \
      resp = `VERIF_BUS_RESP_SOFT; \
      if (!`VERIF_BUS_SIZE_OK(size)) begin \
        data = 32'h0; \
        resp = `VERIF_BUS_RESP_SOFT; \
      end else if (size == 3'd2 && addr[1:0] == 2'd3) begin \
        PRIM_READ(addr, 3'd1, d0, r0); \
        if (`VERIF_BUS_RESP_IS_HARD(r0)) begin \
          data = {24'h0, d0[7:0]}; \
          resp = r0; \
        end else begin \
          PRIM_READ(addr + 32'd1, 3'd1, d1, r1); \
          data = {16'h0, d1[7:0], d0[7:0]}; \
          resp = `VERIF_BUS_RESP_WORSE(r0, r1); \
        end \
      end else if (size == 3'd4 && addr[1:0] != 2'd0) begin \
        PRIM_READ(addr + 0, 3'd1, d0, r0); \
        if (`VERIF_BUS_RESP_IS_HARD(r0)) begin \
          data = {24'h0, d0[7:0]}; \
          resp = r0; \
        end else begin \
          PRIM_READ(addr + 1, 3'd1, d1, r1); \
          if (`VERIF_BUS_RESP_IS_HARD(r1)) begin \
            data = {16'h0, d1[7:0], d0[7:0]}; \
            resp = `VERIF_BUS_RESP_WORSE(r0, r1); \
          end else begin \
            PRIM_READ(addr + 2, 3'd1, d2, r2); \
            if (`VERIF_BUS_RESP_IS_HARD(r2)) begin \
              data = {8'h0, d2[7:0], d1[7:0], d0[7:0]}; \
              resp = `VERIF_BUS_RESP_WORSE(`VERIF_BUS_RESP_WORSE(r0, r1), r2); \
            end else begin \
              PRIM_READ(addr + 3, 3'd1, d3, r3); \
              data = {d3[7:0], d2[7:0], d1[7:0], d0[7:0]}; \
              resp = `VERIF_BUS_RESP_WORSE(`VERIF_BUS_RESP_WORSE(r0, r1), \
                                          `VERIF_BUS_RESP_WORSE(r2, r3)); \
            end \
          end \
        end \
      end else \
        PRIM_READ(addr, size, data, resp); \
    end \
  endtask \
  task bus_write; \
    input  [31:0] addr; \
    input  [31:0] data; \
    input  [2:0]  size; \
    output [1:0]  resp; \
    reg [1:0] r0, r1, r2, r3; \
    begin \
      resp = `VERIF_BUS_RESP_SOFT; \
      if (!`VERIF_BUS_SIZE_OK(size)) begin \
        resp = `VERIF_BUS_RESP_SOFT; \
      end else if (size == 3'd2 && addr[1:0] == 2'd3) begin \
        PRIM_WRITE(addr, {24'h0, data[7:0]}, 3'd1, r0); \
        if (`VERIF_BUS_RESP_IS_HARD(r0)) \
          resp = r0; \
        else begin \
          PRIM_WRITE(addr + 32'd1, {24'h0, data[15:8]}, 3'd1, r1); \
          resp = `VERIF_BUS_RESP_WORSE(r0, r1); \
        end \
      end else if (size == 3'd4 && addr[1:0] != 2'd0) begin \
        PRIM_WRITE(addr + 0, {24'h0, data[7:0]}, 3'd1, r0); \
        if (`VERIF_BUS_RESP_IS_HARD(r0)) \
          resp = r0; \
        else begin \
          PRIM_WRITE(addr + 1, {24'h0, data[15:8]}, 3'd1, r1); \
          if (`VERIF_BUS_RESP_IS_HARD(r1)) \
            resp = `VERIF_BUS_RESP_WORSE(r0, r1); \
          else begin \
            PRIM_WRITE(addr + 2, {24'h0, data[23:16]}, 3'd1, r2); \
            if (`VERIF_BUS_RESP_IS_HARD(r2)) \
              resp = `VERIF_BUS_RESP_WORSE(`VERIF_BUS_RESP_WORSE(r0, r1), r2); \
            else begin \
              PRIM_WRITE(addr + 3, {24'h0, data[31:24]}, 3'd1, r3); \
              resp = `VERIF_BUS_RESP_WORSE(`VERIF_BUS_RESP_WORSE(r0, r1), \
                                          `VERIF_BUS_RESP_WORSE(r2, r3)); \
            end \
          end \
        end \
      end else \
        PRIM_WRITE(addr, data, size, resp); \
    end \
  endtask

`endif
