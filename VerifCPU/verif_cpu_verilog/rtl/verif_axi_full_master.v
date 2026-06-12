// Behavioral AXI3/4/5 full master — single-beat INCR transfers for VerifCPU bus_* API
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_axi_full_master #(
  parameter int AXI_PROT = 4,
  parameter int ID_WIDTH = 4
)(
  input         ACLK,
  input         ARESETn,
  output reg [ID_WIDTH-1:0] ARID,
  output reg [31:0] ARADDR,
  output reg [7:0]  ARLEN,
  output reg [2:0]  ARSIZE,
  output reg [1:0]  ARBURST,
  output reg [3:0]  ARQOS,
  output reg [3:0]  ARREGION,
  output reg        ARVALID,
  input             ARREADY,
  input  [ID_WIDTH-1:0] RID,
  input  [31:0] RDATA,
  input  [1:0]  RRESP,
  input             RLAST,
  input             RVALID,
  output reg        RREADY,
  output reg [ID_WIDTH-1:0] AWID,
  output reg [31:0] AWADDR,
  output reg [7:0]  AWLEN,
  output reg [2:0]  AWSIZE,
  output reg [1:0]  AWBURST,
  output reg [3:0]  AWQOS,
  output reg [3:0]  AWREGION,
  output reg [5:0]  AWATOP,
  output reg        AWVALID,
  input             AWREADY,
  output reg [ID_WIDTH-1:0] WID,
  output reg [31:0] WDATA,
  output reg [3:0]  WSTRB,
  output reg        WLAST,
  output reg        WVALID,
  input             WREADY,
  input  [ID_WIDTH-1:0] BID,
  input  [1:0]  BRESP,
  input             BVALID,
  output reg        BREADY,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  localparam BURST_INCR = 2'b01;

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

  function [3:0] wstrb_for_bytes;
    input [2:0] sz;
    begin
      case (sz)
        3'd1: wstrb_for_bytes = 4'b0001;
        3'd2: wstrb_for_bytes = 4'b0011;
        default: wstrb_for_bytes = 4'b1111;
      endcase
    end
  endfunction

  initial begin
    ARID = 0; ARADDR = 0; ARLEN = 0; ARSIZE = 3'b010; ARBURST = BURST_INCR;
    ARQOS = 0; ARREGION = 0; ARVALID = 0; RREADY = 0;
    AWID = 0; AWADDR = 0; AWLEN = 0; AWSIZE = 3'b010; AWBURST = BURST_INCR;
    AWQOS = 0; AWREGION = 0; AWATOP = 0; AWVALID = 0;
    WID = 0; WDATA = 0; WSTRB = 0; WLAST = 0; WVALID = 0; BREADY = 0;
    snoop_valid = 0; snoop_wr = 0; snoop_addr = 0; snoop_data = 0;
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
      ARID = 0;
      ARADDR = addr;
      ARLEN = 8'd0;
      ARSIZE = axsize_for_bytes(size);
      ARBURST = BURST_INCR;
      ARQOS = 4'd0;
      ARREGION = 4'd0;
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
      while (!(RVALID && RLAST)) begin
        @(posedge ACLK);
        guard = guard + 1;
        if (guard > 64) begin
          RREADY = 1'b0;
          resp = 2'd2;
          disable axi_read;
        end
      end
      data = RDATA;
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
      AWID = 0;
      AWADDR = addr;
      AWLEN = 8'd0;
      AWSIZE = axsize_for_bytes(size);
      AWBURST = BURST_INCR;
      AWQOS = 4'd0;
      AWREGION = 4'd0;
      AWATOP = 6'd0;
      AWVALID = 1'b1;
      WDATA = data;
      WSTRB = wstrb_for_bytes(size);
      WLAST = 1'b1;
      WVALID = 1'b1;
      if (AXI_PROT == 3) WID = 0;
      guard = 0;
      while (!AWREADY || !WREADY) begin
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
    begin axi_read(addr, size, data, resp); end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin axi_write(addr, data, size, resp); end
  endtask

endmodule