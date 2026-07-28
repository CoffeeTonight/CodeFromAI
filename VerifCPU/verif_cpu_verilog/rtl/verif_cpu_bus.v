`timescale 1ns/1ps
// Simple in-memory bus for simulation (mirrors python_model simple_bus.py)
// OS outstanding path: shared SSOT `VERIF_BUS_OS_BLOCKING_BODY`

`include "verif_cpu_defs.vh"
`include "verif_bus_defs.vh"
`include "verif_bus_os_blocking_tasks.vh"

module verif_cpu_bus #(
  parameter BUS_SIZE = 32'h100000
)(
  output reg        txn_valid,
  output reg        txn_is_write,
  output reg [31:0] txn_addr,
  output reg [31:0] txn_data,
  output reg [2:0]  txn_size
);

  // tool: cap_blocking_os=1 cap_multi_outstanding=0 cap_mem_model=1
  reg [7:0] mem [0:BUS_SIZE-1];

  initial begin
    txn_valid    = 1'b0;
    txn_is_write = 1'b0;
    txn_addr     = 32'h0;
    txn_data     = 32'h0;
    txn_size     = 3'd0;
  end

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
      if (!`VERIF_BUS_SIZE_OK(size) ||
          !`VERIF_BUS_SPAN_OK(addr, {29'b0, size}, BUS_SIZE)) begin
        resp = `VERIF_BUS_RESP_SLV;
        $display("[Bus] READ bad size/OOB addr=0x%08h size=%0d", addr, size);
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

  task bus_write;
    input [31:0] addr;
    input [31:0] data;
    input [2:0]  size;
    output [1:0] resp;
    integer i;
    begin
      resp = `VERIF_BUS_RESP_OK;
      if (!`VERIF_BUS_SIZE_OK(size) ||
          !`VERIF_BUS_SPAN_OK(addr, {29'b0, size}, BUS_SIZE)) begin
        resp = `VERIF_BUS_RESP_SLV;
        $display("[Bus] WRITE bad size/OOB addr=0x%08h size=%0d", addr, size);
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

  `VERIF_BUS_OS_BLOCKING_BODY

  // Extend OS reset with mem wipe (local bus only)
  task bus_reset;
    integer i;
    begin
      for (i = 0; i < BUS_SIZE; i = i + 1)
        mem[i] = 8'h0;
      bus_os_reset();
    end
  endtask

endmodule
