// CHI master stub — packet flit placeholders + bus_* API (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_chi_master (
  input         CLK,
  input         RESETn,
  output reg        TXREQFLITV,
  input             TXREQFLITPEND,
  output reg [43:0] TXREQFLIT,
  input             TXRSPFLITV,
  output reg        TXRSPFLITPEND,
  input  [12:0] TXRSPFLIT,
  input             TXDATFLITV,
  output reg        TXDATFLITPEND,
  input  [145:0] TXDATFLIT,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  initial begin
    TXREQFLITV = 1'b0;
    TXREQFLIT = 44'h0;
    TXRSPFLITPEND = 1'b1;
    TXDATFLITPEND = 1'b1;
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