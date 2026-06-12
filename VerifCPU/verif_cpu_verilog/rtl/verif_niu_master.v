// NoC NIU master stub — vendor placeholder + bus_* API (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_niu_master (
  input         CLK,
  input         RESETn,
  output reg        REQ_VALID,
  input             REQ_READY,
  output reg [63:0] REQ_FLIT,
  input             RSP_VALID,
  output reg        RSP_READY,
  input  [63:0] RSP_FLIT,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  initial begin
    REQ_VALID = 1'b0;
    REQ_FLIT = 64'h0;
    RSP_READY = 1'b1;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin
      data = 32'h0;
      resp = 2'd2;
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = 32'h0;
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      resp = 2'd2;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
    end
  endtask

endmodule