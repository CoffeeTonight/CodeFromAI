// Behavioral APB4 master — APB3 + PPROT
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_apb4_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32
)(
  input         PCLK,
  input         PRESETn,
  output reg [ADDR_WIDTH-1:0] PADDR,
  output reg        PSEL,
  output reg        PENABLE,
  output reg        PWRITE,
  output reg [DATA_WIDTH-1:0] PWDATA,
  output reg [DATA_WIDTH/8-1:0] PSTRB,
  output reg [2:0]  PPROT,
  input  [DATA_WIDTH-1:0] PRDATA,
  input         PREADY,
  input         PSLVERR,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);


  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
  initial begin
    PADDR = 32'h0;
    PSEL = 1'b0;
    PENABLE = 1'b0;
    PWRITE = 1'b0;
    PWDATA = 32'h0;
    PSTRB = {STRB_WIDTH{1'b0}};
    PPROT = 3'b000;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task apb_idle;
    begin
      PSEL = 1'b0;
      PENABLE = 1'b0;
      PWRITE = 1'b0;
      PSTRB = {STRB_WIDTH{1'b0}};
      PWDATA = 32'h0;
    end
  endtask

  task apb_xfer;
    input        is_wr;
    input [31:0] addr;
    input [31:0] wdata;
    input [2:0]  size;
    output [31:0] rdata;
    output [1:0]  resp;
    integer guard;
    begin
      resp = 2'd0;
      rdata = 32'h0;
      apb_idle();
      PPROT = 3'b010;
      @(posedge PCLK);
      PADDR = addr;
      PWRITE = is_wr;
      PWDATA = is_wr ? lane_pwdata(wdata, addr, size) : 32'h0;
      PSTRB = is_wr ? lane_wstrb(addr, size) : {STRB_WIDTH{1'b0}};
      PSEL = 1'b1;
      PENABLE = 1'b0;
      @(posedge PCLK);
      PENABLE = 1'b1;
      @(posedge PCLK);
      guard = 0;
      do begin
        @(posedge PCLK);
        `VERIF_BUS_WAIT_TICK(guard, "apb4 bus_xfer PREADY")
      end while (!PREADY);
      #1;
      if (!is_wr)
        rdata = lane_prdata(PRDATA, addr, size);
      resp = PSLVERR ? 2'd2 : 2'd0;
      snoop_valid = 1'b1;
      snoop_wr = is_wr;
      snoop_addr = addr;
      snoop_data = is_wr ? wdata : rdata;
      @(posedge PCLK);
      snoop_valid = 1'b0;
      apb_idle();
    end
  endtask

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin apb_xfer(1'b0, addr, 32'h0, size, data, resp); end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    reg [31:0] dummy;
    begin apb_xfer(1'b1, addr, data, size, dummy, resp); end
  endtask

endmodule