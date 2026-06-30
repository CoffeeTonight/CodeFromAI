// Behavioral AXI4-Lite master — single-beat read/write for VerifCPU integration
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

module verif_axi_lite_master (
  input         ACLK,
  input         ARESETn,
  output reg        ARVALID,
  input             ARREADY,
  output reg [31:0] ARADDR,
  output reg [2:0]  ARSIZE,
  input             RVALID,
  output reg        RREADY,
  input  [31:0] RDATA,
  input  [1:0]  RRESP,
  output reg        AWVALID,
  input             AWREADY,
  output reg [31:0] AWADDR,
  output reg [2:0]  AWSIZE,
  output reg        WVALID,
  input             WREADY,
  output reg [31:0] WDATA,
  output reg [3:0]  WSTRB,
  input             BVALID,
  output reg        BREADY,
  input  [1:0]  BRESP,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  function [2:0] axsize_for_bytes;
    input [2:0] sz;
    begin
      case (sz)
        3'd1: axsize_for_bytes = 3'b000;
        3'd2: axsize_for_bytes = 3'b001;
        default: axsize_for_bytes = 3'b010;
      endcase
    end
  endfunction

  initial begin
    ARVALID = 1'b0;
    ARADDR = 32'h0;
    ARSIZE = 3'b010;
    RREADY = 1'b0;
    AWVALID = 1'b0;
    AWADDR = 32'h0;
    AWSIZE = 3'b010;
    WVALID = 1'b0;
    WDATA = 32'h0;
    WSTRB = 4'h0;
    BREADY = 1'b0;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
  end

  task axi_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    begin
      resp = 2'd0;
      data = 32'h0;
      @(posedge ACLK);
      ARADDR = addr;
      ARSIZE = axsize_for_bytes(size);
      ARVALID = 1'b1;
      guard = 0;
      while (!ARREADY) begin
        @(posedge ACLK);
        guard = guard + 1;
        if (guard > 64) begin
          ARVALID = 1'b0;
          resp = 2'd2;
          disable axi_read;
        end
      end
      @(posedge ACLK);
      ARVALID = 1'b0;
      RREADY = 1'b1;
      guard = 0;
      while (!RVALID) begin
        @(posedge ACLK);
        guard = guard + 1;
        if (guard > 64) begin
          RREADY = 1'b0;
          resp = 2'd2;
          disable axi_read;
        end
      end
      data = lane_prdata(RDATA, addr, size);
      resp = (RRESP != 2'b00) ? 2'd2 : 2'd0;
      @(posedge ACLK);
      RREADY = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b0;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge ACLK);
      snoop_valid = 1'b0;
    end
  endtask

  task axi_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer guard;
    begin
      resp = 2'd0;
      @(posedge ACLK);
      AWADDR = addr;
      AWSIZE = axsize_for_bytes(size);
      AWVALID = 1'b1;
      WDATA = lane_pwdata(data, addr, size);
      WSTRB = lane_wstrb(addr, size);
      WVALID = 1'b1;
      guard = 0;
      while (!AWREADY) begin
        @(posedge ACLK);
        guard = guard + 1;
        if (guard > 64) begin
          AWVALID = 1'b0;
          WVALID = 1'b0;
          resp = 2'd2;
          disable axi_write;
        end
      end
      guard = 0;
      while (!WREADY) begin
        @(posedge ACLK);
        guard = guard + 1;
        if (guard > 64) begin
          AWVALID = 1'b0;
          WVALID = 1'b0;
          resp = 2'd2;
          disable axi_write;
        end
      end
      @(posedge ACLK);
      AWVALID = 1'b0;
      WVALID = 1'b0;
      BREADY = 1'b1;
      guard = 0;
      while (!BVALID) begin
        @(posedge ACLK);
        guard = guard + 1;
        if (guard > 64) begin
          BREADY = 1'b0;
          resp = 2'd2;
          disable axi_write;
        end
      end
      resp = (BRESP != 2'b00) ? 2'd2 : 2'd0;
      @(posedge ACLK);
      BREADY = 1'b0;
      snoop_valid = 1'b1;
      snoop_wr = 1'b1;
      snoop_addr = addr;
      snoop_data = data;
      @(posedge ACLK);
      snoop_valid = 1'b0;
    end
  endtask

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin
      axi_read(addr, size, data, resp);
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      axi_write(addr, data, size, resp);
    end
  endtask

endmodule