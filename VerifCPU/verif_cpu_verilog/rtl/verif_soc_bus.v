// SoC-backed bus adapter for VerifCPU cores (mirrors python_model SocBusAdapter)
// Blocking + outstanding stubs.
// Contract (matches verif_bus_os_blocking_tasks + true OS masters):
//   issue  — queue args (live), not yet complete
//   poll   — if live, perform xfer once and cache; if done, return cache (no re-xfer)
//   wait   — ensure complete, return cache, clear done (reap)

`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_soc_bus;

  reg [31:0] os_rd_addr;
  reg [2:0]  os_rd_size;
  reg        os_rd_live;
  reg        os_rd_done;
  reg [31:0] os_rd_data;
  reg [1:0]  os_rd_resp;
  reg [31:0] os_wr_addr;
  reg [31:0] os_wr_data;
  reg [2:0]  os_wr_size;
  reg        os_wr_live;
  reg        os_wr_done;
  reg [1:0]  os_wr_resp;

  initial begin
    os_rd_live = 1'b0;
    os_rd_done = 1'b0;
    os_wr_live = 1'b0;
    os_wr_done = 1'b0;
  end

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    reg [1:0] port;
    begin
`ifdef VERIF_SOC_DUT_HUB
      `VERIF_SOC_DUT_HUB.decode_read(addr, size, data, resp, port);
`else
      data = 32'h0;
      resp = 2'd2;
      port = 2'd3;
`endif
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    reg [1:0] port;
    begin
`ifdef VERIF_SOC_DUT_HUB
      `VERIF_SOC_DUT_HUB.decode_write(addr, data, size, resp, port);
`else
      resp = 2'd2;
      port = 2'd3;
`endif
    end
  endtask

  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      if (os_rd_live || os_rd_done) begin
        handle = -1;
        ok = 1'b0;
      end else begin
        os_rd_addr = addr;
        os_rd_size = size;
        os_rd_live = 1'b1;
        os_rd_done = 1'b0;
        handle = 0;
        ok = 1'b1;
      end
    end
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      if (handle != 0) begin
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
        done = 1'b0;
      end else begin
        if (os_rd_live) begin
          bus_read(os_rd_addr, os_rd_size, os_rd_data, os_rd_resp);
          os_rd_live = 1'b0;
          os_rd_done = 1'b1;
        end
        if (os_rd_done) begin
          data = os_rd_data;
          resp = os_rd_resp;
          done = 1'b1;
        end else begin
          data = 32'h0;
          resp = `VERIF_BUS_RESP_SOFT;
          done = 1'b0;
        end
      end
    end
  endtask

  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    reg done;
    begin
      bus_read_poll(handle, data, resp, done);
      if (!done) begin
        data = 32'hDEADDEAD;
        resp = `VERIF_BUS_RESP_SOFT;
      end else
        os_rd_done = 1'b0;
    end
  endtask

  task bus_write_issue;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      if (os_wr_live || os_wr_done) begin
        handle = -1;
        ok = 1'b0;
      end else begin
        os_wr_addr = addr;
        os_wr_data = data;
        os_wr_size = size;
        os_wr_live = 1'b1;
        os_wr_done = 1'b0;
        handle = 0;
        ok = 1'b1;
      end
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      if (handle != 0) begin
        resp = `VERIF_BUS_RESP_SOFT;
        done = 1'b0;
      end else begin
        if (os_wr_live) begin
          bus_write(os_wr_addr, os_wr_data, os_wr_size, os_wr_resp);
          os_wr_live = 1'b0;
          os_wr_done = 1'b1;
        end
        if (os_wr_done) begin
          resp = os_wr_resp;
          done = 1'b1;
        end else begin
          resp = `VERIF_BUS_RESP_SOFT;
          done = 1'b0;
        end
      end
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    reg done;
    begin
      bus_write_poll(handle, resp, done);
      if (!done)
        resp = `VERIF_BUS_RESP_SOFT;
      else
        os_wr_done = 1'b0;
    end
  endtask

  task bus_read_outstanding_count;
    output integer n;
    begin n = (os_rd_live || os_rd_done) ? 1 : 0; end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin n = (os_wr_live || os_wr_done) ? 1 : 0; end
  endtask

  task bus_reset;
    begin
      os_rd_live = 1'b0;
      os_rd_done = 1'b0;
      os_wr_live = 1'b0;
      os_wr_done = 1'b0;
    end
  endtask

endmodule
