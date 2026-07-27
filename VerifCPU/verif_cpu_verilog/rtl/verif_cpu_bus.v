// Simple in-memory bus for simulation (mirrors python_model simple_bus.py)

`include "verif_cpu_defs.vh"
`include "verif_bus_defs.vh"

module verif_cpu_bus #(
  parameter BUS_SIZE = 32'h100000
)(
  // Transaction recorder hook (optional, driven by parent)
  output reg        txn_valid,
  output reg        txn_is_write,
  output reg [31:0] txn_addr,
  output reg [31:0] txn_data,
  output reg [2:0]  txn_size
);

  reg [7:0] mem [0:BUS_SIZE-1];
  // OS stubs: issue → live; poll completes once → done; wait reaps done
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
    txn_valid    = 1'b0;
    txn_is_write = 1'b0;
    txn_addr     = 32'h0;
    txn_data     = 32'h0;
    txn_size     = 3'd0;
    os_rd_live   = 1'b0;
    os_rd_done   = 1'b0;
    os_wr_live   = 1'b0;
    os_wr_done   = 1'b0;
  end

  task bus_reset;
    integer i;
    begin
      for (i = 0; i < BUS_SIZE; i = i + 1)
        mem[i] = 8'h0;
      os_rd_live = 1'b0;
      os_rd_done = 1'b0;
      os_wr_live = 1'b0;
      os_wr_done = 1'b0;
    end
  endtask

  task bus_load_byte;
    input [31:0] addr;
    input [7:0]  data;
    begin
      if (addr < BUS_SIZE)
        mem[addr] = data;
    end
  endtask

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer i;
    reg [31:0] tmp;
    begin
      resp = `VERIF_BUS_RESP_OK;
      data = 32'h0;
      if (!`VERIF_BUS_SPAN_OK(addr, {29'b0, size}, BUS_SIZE)) begin
        resp = `VERIF_BUS_RESP_SLV;
        $display("[Bus] READ out of bounds addr=0x%08h size=%0d", addr, size);
      end else begin
        tmp = 32'h0;
        for (i = 0; i < size; i = i + 1)
          tmp[i*8 +: 8] = mem[addr + i];
        data = tmp;
        txn_is_write = 1'b0;
        txn_addr     = addr;
        txn_data     = data;
        txn_size     = size;
        txn_valid    = 1'b1;
        #1 txn_valid    = 1'b0;
      end
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

  task bus_write;
    input [31:0] addr;
    input [31:0] data;
    input [2:0]  size;
    output [1:0] resp;
    integer i;
    begin
      resp = `VERIF_BUS_RESP_OK;
      if (!`VERIF_BUS_SPAN_OK(addr, {29'b0, size}, BUS_SIZE)) begin
        resp = `VERIF_BUS_RESP_SLV;
        $display("[Bus] WRITE out of bounds addr=0x%08h size=%0d", addr, size);
      end else begin
        for (i = 0; i < size; i = i + 1)
          mem[addr + i] = data[i*8 +: 8];
        txn_is_write = 1'b1;
        txn_addr     = addr;
        txn_data     = data;
        txn_size     = size;
        txn_valid    = 1'b1;
        #1 txn_valid    = 1'b0;
      end
    end
  endtask

endmodule