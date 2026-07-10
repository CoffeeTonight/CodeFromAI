// Behavioral AHB-Lite master — single NONSEQ transfers for VerifCPU integration
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_ahb_lite_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32
)(
  input         HCLK,
  input         HRESETn,
  output reg [ADDR_WIDTH-1:0] HADDR,
  output reg [2:0]  HSIZE,
  output reg [1:0]  HTRANS,
  output reg        HWRITE,
  output reg [DATA_WIDTH-1:0] HWDATA,
  input         HREADY,
  input  [DATA_WIDTH-1:0] HRDATA,
  input  [1:0]  HRESP,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);


  localparam int STRB_WIDTH = DATA_WIDTH / 8;
  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)
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
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task ahb_idle;
    begin
      HTRANS = HTRANS_IDLE;
      HWRITE = 1'b0;
      HWDATA = 32'h0;
    end
  endtask

  task ahb_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    begin
      resp = 2'd0;
      data = 32'h0;
      ahb_idle();
      @(posedge HCLK);
      HADDR = addr;
      HSIZE = hsize_for_bytes(size);
      HWRITE = 1'b0;
      HWDATA = 32'h0;
      HTRANS = HTRANS_NONSEQ;
      @(posedge HCLK);
      guard = 0;
      do begin
        @(posedge HCLK);
        `VERIF_BUS_WAIT_TICK(guard, "ahb_lite bus_read HREADY")
      end while (!HREADY);
      #1;
      data = lane_prdata(HRDATA, addr, size);
      resp = (HRESP != 2'b00) ? 2'd2 : 2'd0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge HCLK);
      snoop_valid = 1'b0;
      ahb_idle();
    end
  endtask

  task ahb_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer guard;
    begin
      resp = 2'd0;
      ahb_idle();
      @(posedge HCLK);
      HADDR = addr;
      HSIZE = hsize_for_bytes(size);
      HWRITE = 1'b1;
      HWDATA = lane_pwdata(data, addr, size);
      HTRANS = HTRANS_NONSEQ;
      @(posedge HCLK);
      guard = 0;
      do begin
        @(posedge HCLK);
        `VERIF_BUS_WAIT_TICK(guard, "ahb_lite bus_write HREADY")
      end while (!HREADY);
      #1;
      resp = (HRESP != 2'b00) ? 2'd2 : 2'd0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
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
    begin
      ahb_read(addr, size, data, resp);
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      ahb_write(addr, data, size, resp);
    end
  endtask

endmodule