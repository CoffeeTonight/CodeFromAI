// Behavioral AHB5-Lite master — AHB-Lite + HNONSEC / HEXCL
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_ahb5_lite_master (
  input         HCLK,
  input         HRESETn,
  output reg [31:0] HADDR,
  output reg [2:0]  HSIZE,
  output reg [1:0]  HTRANS,
  output reg        HWRITE,
  output reg [31:0] HWDATA,
  output reg        HREADY,
  output reg        HNONSEC,
  output reg        HEXCL,
  input             HEXOK,
  input  [31:0] HRDATA,
  input         HREADYOUT,
  input  [1:0]  HRESP,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  localparam HTRANS_IDLE   = 2'b00;
  localparam HTRANS_NONSEQ = 2'b10;

  function [2:0] hsize_for_bytes;
    input [2:0] sz;
    begin
      case (sz)
        3'd1: hsize_for_bytes = 3'b000;
        3'd2: hsize_for_bytes = 3'b001;
        default: hsize_for_bytes = 3'b010;
      endcase
    end
  endfunction

  initial begin
    HADDR = 32'h0;
    HSIZE = 3'b010;
    HTRANS = HTRANS_IDLE;
    HWRITE = 1'b0;
    HWDATA = 32'h0;
    HREADY = 1'b1;
    HNONSEC = 1'b1;
    HEXCL = 1'b0;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task ahb_idle;
    begin
      HTRANS = HTRANS_IDLE;
      HWRITE = 1'b0;
      HEXCL = 1'b0;
    end
  endtask

  task ahb_xfer;
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
      HNONSEC = 1'b1;
      HEXCL = 1'b0;
      @(posedge HCLK);
      HADDR = addr;
      HSIZE = hsize_for_bytes(size);
      HWRITE = is_wr;
      HWDATA = wdata;
      HTRANS = HTRANS_NONSEQ;
      guard = 0;
      while (!HREADYOUT) begin
        @(posedge HCLK);
        guard = guard + 1;
        if (guard > 64) begin
          resp = 2'd2;
          ahb_idle();
          disable ahb_xfer;
        end
      end
      @(posedge HCLK);
      #1;
      if (!is_wr) rdata = HRDATA;
      resp = (HRESP != 2'b00) ? 2'd2 : 2'd0;
      snoop_valid = 1'b1;
      snoop_wr = is_wr;
      snoop_addr = addr;
      snoop_data = is_wr ? wdata : rdata;
      @(posedge HCLK);
      snoop_valid = 1'b0;
      ahb_idle();
    end
  endtask

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin ahb_xfer(1'b0, addr, 32'h0, size, data, resp); end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    reg [31:0] dummy;
    begin ahb_xfer(1'b1, addr, data, size, dummy, resp); end
  endtask

endmodule