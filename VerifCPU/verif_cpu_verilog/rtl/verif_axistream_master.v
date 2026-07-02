// AXI4-Stream master stub — stream port + bus_* API (returns SLVERR; not memory-mapped)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_axistream_master #(
  parameter int DATA_WIDTH = 32
)(
  input         ACLK,
  input         ARESETn,
  output reg        TVALID,
  input             TREADY,
  output reg [DATA_WIDTH-1:0] TDATA,
  output reg        TLAST,
  output reg [DATA_WIDTH/8-1:0] TKEEP,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  initial begin
    TVALID = 1'b0;
    TDATA = 32'h0;
    TLAST = 1'b0;
    TKEEP = 4'hF;
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
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = 32'h0;
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
      resp = 2'd2;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
      snoop_valid = 1'b1;
      #1;
      snoop_valid = 1'b0;
    end
  endtask

endmodule