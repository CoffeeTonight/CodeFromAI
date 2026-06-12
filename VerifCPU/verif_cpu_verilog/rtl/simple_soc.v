// Simple SoC — 1:3 address decoder (SFR / SRAM / UART) behavior model

`timescale 1ns/1ps
`include "soc_init_seq.vh"

module simple_soc_slave #(
  parameter [31:0] BASE = 32'h0,
  parameter [31:0] SIZE = 32'h1000
)();

  reg [7:0] mem [0:65535];
  integer i;

  initial begin
    for (i = 0; i < SIZE; i = i + 1)
      mem[i] = 8'h0;
  end

  task slave_read;
    input  [31:0] a;
    input  [2:0]  sz;
    output [31:0] d;
    output [1:0]  r;
    integer j;
    reg [31:0] tmp;
    begin
      r = 2'd0;
      d = 32'h0;
      if (a < BASE || a + sz > BASE + SIZE) begin
        r = 2'd2;
        d = 32'hDEAD_DEAD;
      end else begin
        tmp = 32'h0;
        for (j = 0; j < sz; j = j + 1)
          tmp[j*8 +: 8] = mem[(a - BASE) + j];
        d = tmp;
        // X/Z test port (SFR 0x4000_00FC) — low byte is X for sanitize test
        if (BASE == 32'h4000_0000 && (a - BASE) == 32'h0FC && sz == 3'd4)
          d[7:0] = 8'bxxxxxxxx;
      end
    end
  endtask

  task slave_write;
    input  [31:0] a;
    input  [31:0] d;
    input  [2:0]  sz;
    output [1:0]  r;
    integer j;
    begin
      r = 2'd0;
      if (a < BASE || a + sz > BASE + SIZE)
        r = 2'd2;
      else begin
        for (j = 0; j < sz; j = j + 1)
          mem[(a - BASE) + j] = d[j*8 +: 8];
      end
    end
  endtask

endmodule


module simple_soc;

  simple_soc_slave #(.BASE(32'h4000_0000), .SIZE(32'h1000))  u_sfr  ();
  simple_soc_slave #(.BASE(32'h8000_0000), .SIZE(32'h10000)) u_sram ();
  simple_soc_slave #(.BASE(32'hC000_0000), .SIZE(32'h1000))  u_uart ();

  reg        stxn_valid [0:2];
  reg        stxn_wr    [0:2];
  reg [31:0] stxn_addr  [0:2];
  reg [31:0] stxn_data  [0:2];

  integer p;

  initial begin
    for (p = 0; p < 3; p = p + 1) begin
      stxn_valid[p] = 1'b0;
      stxn_wr[p]    = 1'b0;
      stxn_addr[p]  = 32'h0;
      stxn_data[p]  = 32'h0;
    end
  end

  task pulse_snoop;
    input [1:0]  port;
    input        wr;
    input [31:0] a;
    input [31:0] d;
    begin
      stxn_valid[port] = 1'b1;
      stxn_wr[port]    = wr;
      stxn_addr[port]  = a;
      stxn_data[port]  = d;
      #1 stxn_valid[port] = 1'b0;
    end
  endtask

  task decode_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    output [1:0]  port;
    begin
      port = 2'd3;
      data = 32'hDEAD_DEAD;
      resp = 2'd2;
      if (addr >= 32'h4000_0000 && addr < 32'h4000_1000) begin
        port = 2'd0;
        u_sfr.slave_read(addr, size, data, resp);
        pulse_snoop(0, 1'b0, addr, data);
      end else if (addr >= 32'h8000_0000 && addr < 32'h8001_0000) begin
        port = 2'd1;
        u_sram.slave_read(addr, size, data, resp);
        pulse_snoop(1, 1'b0, addr, data);
      end else if (addr >= 32'hC000_0000 && addr < 32'hC000_1000) begin
        port = 2'd2;
        u_uart.slave_read(addr, size, data, resp);
        pulse_snoop(2, 1'b0, addr, data);
      end
    end
  endtask

  task decode_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    output [1:0]  port;
    begin
      port = 2'd3;
      resp = 2'd2;
      if (addr >= 32'h4000_0000 && addr < 32'h4000_1000) begin
        port = 2'd0;
        u_sfr.slave_write(addr, data, size, resp);
        pulse_snoop(0, 1'b1, addr, data);
      end else if (addr >= 32'h8000_0000 && addr < 32'h8001_0000) begin
        port = 2'd1;
        u_sram.slave_write(addr, data, size, resp);
        pulse_snoop(1, 1'b1, addr, data);
      end else if (addr >= 32'hC000_0000 && addr < 32'hC000_1000) begin
        port = 2'd2;
        u_uart.slave_write(addr, data, size, resp);
        pulse_snoop(2, 1'b1, addr, data);
      end
    end
  endtask

  task run_init;
    reg [1:0] r;
    reg [1:0] p;
    reg [31:0] rd;
    begin
      $display("[SoC] init sequence start (%0d steps from soc_init_seq.h)", `SOC_INIT_STEP_COUNT);
      `SOC_INIT_RUN_STEPS
      $display("[SoC] init sequence done (%0d steps)", `SOC_INIT_STEP_COUNT);
    end
  endtask

endmodule