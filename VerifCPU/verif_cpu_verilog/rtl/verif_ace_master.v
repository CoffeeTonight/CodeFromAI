// ACE master stub — AXI4 full + coherency port placeholders (smoke / manifest)
`timescale 1ns/1ps
`include "verif_bus_defs.vh"

module verif_ace_master #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int AXI_PROT = 4,
  parameter int ID_WIDTH = 4,
  parameter int MAX_OUTSTANDING = 4
)(
  input         ACLK,
  input         ARESETn,
  output wire [ID_WIDTH-1:0] ARID,
  output wire [ADDR_WIDTH-1:0] ARADDR,
  output wire [7:0]  ARLEN,
  output wire [2:0]  ARSIZE,
  output wire [1:0]  ARBURST,
  output wire [2:0]  ARPROT,
  output wire [3:0]  ARQOS,
  output wire [3:0]  ARREGION,
  output wire        ARVALID,
  input              ARREADY,
  input  [ID_WIDTH-1:0] RID,
  input  [DATA_WIDTH-1:0] RDATA,
  input  [1:0]  RRESP,
  input              RLAST,
  input              RVALID,
  output wire        RREADY,
  output wire [ID_WIDTH-1:0] AWID,
  output wire [ADDR_WIDTH-1:0] AWADDR,
  output wire [7:0]  AWLEN,
  output wire [2:0]  AWSIZE,
  output wire [1:0]  AWBURST,
  output wire [2:0]  AWPROT,
  output wire [3:0]  AWQOS,
  output wire [3:0]  AWREGION,
  output wire [5:0]  AWATOP,
  output wire        AWVALID,
  input              AWREADY,
  output wire [ID_WIDTH-1:0] WID,
  output wire [DATA_WIDTH-1:0] WDATA,
  output wire [DATA_WIDTH/8-1:0] WSTRB,
  output wire        WLAST,
  output wire        WVALID,
  input              WREADY,
  input  [ID_WIDTH-1:0] BID,
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

  verif_axi_full_master #(
    .ADDR_WIDTH(ADDR_WIDTH), .DATA_WIDTH(DATA_WIDTH), .AXI_PROT(AXI_PROT),
    .ID_WIDTH(ID_WIDTH), .MAX_OUTSTANDING(MAX_OUTSTANDING)
  ) u_axi (
    .ACLK(ACLK), .ARESETn(ARESETn),
    .ARID(ARID), .ARADDR(ARADDR), .ARLEN(ARLEN), .ARSIZE(ARSIZE), .ARBURST(ARBURST),
    .ARPROT(ARPROT), .ARQOS(ARQOS), .ARREGION(ARREGION), .ARVALID(ARVALID), .ARREADY(ARREADY),
    .RID(RID), .RDATA(RDATA), .RRESP(RRESP), .RLAST(RLAST), .RVALID(RVALID), .RREADY(RREADY),
    .AWID(AWID), .AWADDR(AWADDR), .AWLEN(AWLEN), .AWSIZE(AWSIZE), .AWBURST(AWBURST),
    .AWPROT(AWPROT), .AWQOS(AWQOS), .AWREGION(AWREGION), .AWATOP(AWATOP), .AWVALID(AWVALID), .AWREADY(AWREADY),
    .WID(WID), .WDATA(WDATA), .WSTRB(WSTRB), .WLAST(WLAST), .WVALID(WVALID), .WREADY(WREADY),
    .BID(BID), .BRESP(BRESP), .BVALID(BVALID), .BREADY(BREADY),
    .snoop_valid(snoop_valid), .snoop_wr(snoop_wr),
    .snoop_addr(snoop_addr), .snoop_data(snoop_data)
  );

  assign ACVALID = 1'b0;
  assign ACREADY_OUT = 1'b1;

  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin u_axi.bus_read_issue(addr, size, handle, ok); end
  endtask
  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    begin u_axi.bus_read_wait(handle, data, resp); end
  endtask
  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin u_axi.bus_read_poll(handle, data, resp, done); end
  endtask
  task bus_write_issue;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin u_axi.bus_write_issue(addr, data, size, handle, ok); end
  endtask
  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    begin u_axi.bus_write_wait(handle, resp); end
  endtask
  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin u_axi.bus_write_poll(handle, resp, done); end
  endtask
  task bus_read_outstanding_count;
    output integer n;
    begin u_axi.bus_read_outstanding_count(n); end
  endtask
  task bus_write_outstanding_count;
    output integer n;
    begin u_axi.bus_write_outstanding_count(n); end
  endtask
  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin u_axi.bus_read(addr, size, data, resp); end
  endtask
  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin u_axi.bus_write(addr, data, size, resp); end
  endtask

endmodule