// ACE-Lite master stub — AXI4-Lite + snoop port placeholders (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_ace_lite_master (
  input         ACLK,
  input         ARESETn,
  output wire        ARVALID,
  input              ARREADY,
  output wire [31:0] ARADDR,
  output wire [2:0]  ARSIZE,
  input              RVALID,
  output wire        RREADY,
  input  [31:0] RDATA,
  input  [1:0]  RRESP,
  output wire        AWVALID,
  input              AWREADY,
  output wire [31:0] AWADDR,
  output wire [2:0]  AWSIZE,
  output wire        WVALID,
  input              WREADY,
  output wire [31:0] WDATA,
  output wire [3:0]  WSTRB,
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

  verif_axi_lite_master u_axi (
    .ACLK(ACLK), .ARESETn(ARESETn),
    .ARVALID(ARVALID), .ARREADY(ARREADY), .ARADDR(ARADDR), .ARSIZE(ARSIZE),
    .RVALID(RVALID), .RREADY(RREADY), .RDATA(RDATA), .RRESP(RRESP),
    .AWVALID(AWVALID), .AWREADY(AWREADY), .AWADDR(AWADDR), .AWSIZE(AWSIZE),
    .WVALID(WVALID), .WREADY(WREADY), .WDATA(WDATA), .WSTRB(WSTRB),
    .BVALID(BVALID), .BREADY(BREADY), .BRESP(BRESP),
    .snoop_valid(snoop_valid), .snoop_wr(snoop_wr),
    .snoop_addr(snoop_addr), .snoop_data(snoop_data)
  );

  assign ACVALID = 1'b0;
  assign ACREADY_OUT = 1'b1;

endmodule