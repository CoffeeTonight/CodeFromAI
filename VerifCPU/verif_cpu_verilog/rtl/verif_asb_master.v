// ASB master stub — AMBA2 legacy + bus_* API (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_asb_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32
)(
  input         CLK,
  input         RESETn,
  output reg [ADDR_WIDTH-1:0] ADDR,
  output reg        BWRITE,
  output reg [DATA_WIDTH-1:0] DATA,
  input  [DATA_WIDTH-1:0] RDATA,
  input             READY,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  initial begin
    ADDR = {ADDR_WIDTH{1'b0}};
    BWRITE = 1'b0;
    DATA = {DATA_WIDTH{1'b0}};
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
      data = RDATA;
      resp = 2'd2;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = data;
      snoop_valid = 1'b1;
      #1;
      snoop_valid = 1'b0;
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      ADDR = addr;
      DATA = data;
      BWRITE = 1'b1;
      resp = 2'd2;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
      snoop_valid = 1'b1;
      #1;
      BWRITE = 1'b0;
      snoop_valid = 1'b0;
    end
  endtask

endmodule