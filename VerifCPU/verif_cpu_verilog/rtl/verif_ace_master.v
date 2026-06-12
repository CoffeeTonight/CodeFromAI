// ACE master stub — AXI4 full + coherency port placeholders (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_ace_master #(
  parameter int AXI_PROT = 4
)(
  input         ACLK,
  input         ARESETn,
  output wire [3:0]  ARID,
  output wire [31:0] ARADDR,
  output wire [7:0]  ARLEN,
  output wire [2:0]  ARSIZE,
  output wire [1:0]  ARBURST,
  output wire [3:0]  ARQOS,
  output wire [3:0]  ARREGION,
  output wire        ARVALID,
  input              ARREADY,
  input  [3:0]  RID,
  input  [31:0] RDATA,
  input  [1:0]  RRESP,
  input              RLAST,
  input              RVALID,
  output wire        RREADY,
  output wire [3:0]  AWID,
  output wire [31:0] AWADDR,
  output wire [7:0]  AWLEN,
  output wire [2:0]  AWSIZE,
  output wire [1:0]  AWBURST,
  output wire [3:0]  AWQOS,
  output wire [3:0]  AWREGION,
  output wire [5:0]  AWATOP,
  output wire        AWVALID,
  input              AWREADY,
  output wire [3:0]  WID,
  output wire [31:0] WDATA,
  output wire [3:0]  WSTRB,
  output wire        WLAST,
  output wire        WVALID,
  input              WREADY,
  input  [3:0]  BID,
  input  [1:0]  BRESP,
  input              BVALID,
  output wire        BREADY,
  output wire        ACVALID,
  input              ACREADY,
  input  [3:0]  ACRRESP,
  input  [2:0]  ACSIZE,
  input              ACVALID_IN,
  output wire        ACREADY_OUT,
  output wire        snoop_valid,
  output wire        snoop_wr,
  output wire [31:0] snoop_addr,
  output wire [31:0] snoop_data
);

  verif_axi_full_master #(.AXI_PROT(AXI_PROT)) u_axi (
    .ACLK(ACLK), .ARESETn(ARESETn),
    .ARID(ARID), .ARADDR(ARADDR), .ARLEN(ARLEN), .ARSIZE(ARSIZE), .ARBURST(ARBURST),
    .ARQOS(ARQOS), .ARREGION(ARREGION), .ARVALID(ARVALID), .ARREADY(ARREADY),
    .RID(RID), .RDATA(RDATA), .RRESP(RRESP), .RLAST(RLAST), .RVALID(RVALID), .RREADY(RREADY),
    .AWID(AWID), .AWADDR(AWADDR), .AWLEN(AWLEN), .AWSIZE(AWSIZE), .AWBURST(AWBURST),
    .AWQOS(AWQOS), .AWREGION(AWREGION), .AWATOP(AWATOP), .AWVALID(AWVALID), .AWREADY(AWREADY),
    .WID(WID), .WDATA(WDATA), .WSTRB(WSTRB), .WLAST(WLAST), .WVALID(WVALID), .WREADY(WREADY),
    .BID(BID), .BRESP(BRESP), .BVALID(BVALID), .BREADY(BREADY),
    .snoop_valid(snoop_valid), .snoop_wr(snoop_wr),
    .snoop_addr(snoop_addr), .snoop_data(snoop_data)
  );

  assign ACVALID = 1'b0;
  assign ACREADY_OUT = 1'b1;

endmodule