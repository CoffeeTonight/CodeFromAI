// ACE-Lite master stub — AXI4-Lite + snoop port placeholders (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_ace_lite_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32
)(
  input         ACLK,
  input         ARESETn,
  output wire        ARVALID,
  input              ARREADY,
  output wire [ADDR_WIDTH-1:0] ARADDR,
  output wire [2:0]  ARSIZE,
  output wire [2:0]  ARPROT,
  input              RVALID,
  output wire        RREADY,
  input  [DATA_WIDTH-1:0] RDATA,
  input  [1:0]  RRESP,
  output wire        AWVALID,
  input              AWREADY,
  output wire [ADDR_WIDTH-1:0] AWADDR,
  output wire [2:0]  AWSIZE,
  output wire [2:0]  AWPROT,
  output wire        WVALID,
  input              WREADY,
  output wire [DATA_WIDTH-1:0] WDATA,
  output wire [DATA_WIDTH/8-1:0] WSTRB,
  input              BVALID,
  output wire        BREADY,
  input  [1:0]  BRESP,
  output wire        ACVALID,
  input              ACREADY,
  input  [2:0]  ACSIZE,
  input              ACVALID_IN,
  output wire        ACREADY_OUT,
  output wire        snoop_valid,
  output wire        snoop_wr,
  output wire [31:0] snoop_addr,
  output wire [31:0] snoop_data
);

  verif_axi_lite_master #(.ADDR_WIDTH(ADDR_WIDTH), .DATA_WIDTH(DATA_WIDTH)) u_axi (
    .ACLK(ACLK), .ARESETn(ARESETn),
    .ARVALID(ARVALID), .ARREADY(ARREADY), .ARADDR(ARADDR), .ARSIZE(ARSIZE), .ARPROT(ARPROT),
    .RVALID(RVALID), .RREADY(RREADY), .RDATA(RDATA), .RRESP(RRESP),
    .AWVALID(AWVALID), .AWREADY(AWREADY), .AWADDR(AWADDR), .AWSIZE(AWSIZE), .AWPROT(AWPROT),
    .WVALID(WVALID), .WREADY(WREADY), .WDATA(WDATA), .WSTRB(WSTRB),
    .BVALID(BVALID), .BREADY(BREADY), .BRESP(BRESP),
    .snoop_valid(snoop_valid), .snoop_wr(snoop_wr),
    .snoop_addr(snoop_addr), .snoop_data(snoop_data)
  );

  assign ACVALID = 1'b0;
  assign ACREADY_OUT = 1'b1;

endmodule