// Blocking outstanding stubs for masters with only blocking bus_read/bus_write.
// Contract (matches true OS + CPU core):
//   issue  — queue args (live), not yet complete
//   poll   — if live, perform xfer once and cache; if done, return cache (no re-xfer)
//   wait   — ensure complete, return cache, clear done (reap)
// Prerequisites: bus_read / bus_write already defined; verif_bus_defs.vh for RESP_SOFT.
`ifndef VERIF_BUS_OS_BLOCKING_TASKS_VH
`define VERIF_BUS_OS_BLOCKING_TASKS_VH

`define VERIF_BUS_OS_BLOCKING_IMPL \
  reg [31:0] os_blk_rd_addr; \
  reg [2:0]  os_blk_rd_size; \
  reg        os_blk_rd_live; \
  reg        os_blk_rd_done; \
  reg [31:0] os_blk_rd_data; \
  reg [1:0]  os_blk_rd_resp; \
  reg [31:0] os_blk_wr_addr; \
  reg [31:0] os_blk_wr_data; \
  reg [2:0]  os_blk_wr_size; \
  reg        os_blk_wr_live; \
  reg        os_blk_wr_done; \
  reg [1:0]  os_blk_wr_resp; \
  \
  initial begin \
    os_blk_rd_live = 1'b0; \
    os_blk_rd_done = 1'b0; \
    os_blk_wr_live = 1'b0; \
    os_blk_wr_done = 1'b0; \
  end \
  \
  task bus_reset; \
    begin \
      os_blk_rd_live = 1'b0; \
      os_blk_rd_done = 1'b0; \
      os_blk_wr_live = 1'b0; \
      os_blk_wr_done = 1'b0; \
    end \
  endtask \
  \
  task bus_read_issue; \
    input  [31:0] addr; \
    input  [2:0]  size; \
    output integer handle; \
    output        ok; \
    begin \
      if (os_blk_rd_live || os_blk_rd_done) begin \
        handle = -1; \
        ok = 1'b0; \
      end else begin \
        os_blk_rd_addr = addr; \
        os_blk_rd_size = size; \
        os_blk_rd_live = 1'b1; \
        os_blk_rd_done = 1'b0; \
        handle = 0; \
        ok = 1'b1; \
      end \
    end \
  endtask \
  \
  task bus_read_poll; \
    input  integer handle; \
    output [31:0] data; \
    output [1:0]  resp; \
    output        done; \
    begin \
      if (handle != 0) begin \
        data = 32'h0; \
        resp = `VERIF_BUS_RESP_SOFT; \
        done = 1'b0; \
      end else begin \
      if (os_blk_rd_live) begin \
        bus_read(os_blk_rd_addr, os_blk_rd_size, os_blk_rd_data, os_blk_rd_resp); \
        os_blk_rd_live = 1'b0; \
        os_blk_rd_done = 1'b1; \
      end \
      if (os_blk_rd_done) begin \
        data = os_blk_rd_data; \
        resp = os_blk_rd_resp; \
        done = 1'b1; \
      end else begin \
        data = 32'h0; \
        resp = `VERIF_BUS_RESP_SOFT; \
        done = 1'b0; \
      end \
      end \
    end \
  endtask \
  \
  task bus_read_wait; \
    input  integer handle; \
    output [31:0] data; \
    output [1:0]  resp; \
    reg done; \
    begin \
      bus_read_poll(handle, data, resp, done); \
      if (!done) begin \
        data = 32'hDEADDEAD; \
        resp = `VERIF_BUS_RESP_SOFT; \
      end else begin \
        /* reap so next issue can proceed */ \
        os_blk_rd_done = 1'b0; \
      end \
    end \
  endtask \
  \
  task bus_read_outstanding_count; \
    output integer n; \
    begin n = (os_blk_rd_live || os_blk_rd_done) ? 1 : 0; end \
  endtask \
  \
  task bus_write_issue; \
    input  [31:0] addr; \
    input  [31:0] data; \
    input  [2:0]  size; \
    output integer handle; \
    output        ok; \
    begin \
      if (os_blk_wr_live || os_blk_wr_done) begin \
        handle = -1; \
        ok = 1'b0; \
      end else begin \
        os_blk_wr_addr = addr; \
        os_blk_wr_data = data; \
        os_blk_wr_size = size; \
        os_blk_wr_live = 1'b1; \
        os_blk_wr_done = 1'b0; \
        handle = 0; \
        ok = 1'b1; \
      end \
    end \
  endtask \
  \
  task bus_write_poll; \
    input  integer handle; \
    output [1:0] resp; \
    output       done; \
    begin \
      if (handle != 0) begin \
        resp = `VERIF_BUS_RESP_SOFT; \
        done = 1'b0; \
      end else begin \
      if (os_blk_wr_live) begin \
        bus_write(os_blk_wr_addr, os_blk_wr_data, os_blk_wr_size, os_blk_wr_resp); \
        os_blk_wr_live = 1'b0; \
        os_blk_wr_done = 1'b1; \
      end \
      if (os_blk_wr_done) begin \
        resp = os_blk_wr_resp; \
        done = 1'b1; \
      end else begin \
        resp = `VERIF_BUS_RESP_SOFT; \
        done = 1'b0; \
      end \
      end \
    end \
  endtask \
  \
  task bus_write_wait; \
    input  integer handle; \
    output [1:0] resp; \
    reg done; \
    begin \
      bus_write_poll(handle, resp, done); \
      if (!done) \
        resp = `VERIF_BUS_RESP_SOFT; \
      else \
        os_blk_wr_done = 1'b0; \
    end \
  endtask \
  \
  task bus_write_outstanding_count; \
    output integer n; \
    begin n = (os_blk_wr_live || os_blk_wr_done) ? 1 : 0; end \
  endtask

`endif
