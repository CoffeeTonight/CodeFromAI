// Simple AXI3/4/5 full slave — single-beat read/write
`timescale 1ns/1ps

module verif_axi_full_slave_simple #(
  parameter int ID_WIDTH = 4,
  parameter [31:0] BASE = 32'hA000_0000,
  parameter [31:0] SIZE = 32'h1000,
  parameter [31:0] INIT_WORD0 = 32'h000000A3,
  parameter [31:0] INIT_WORD1 = 32'h00000000
)(
  input         ACLK,
  input         ARESETn,
  input  [ID_WIDTH-1:0] ARID,
  input  [31:0] ARADDR,
  input  [7:0]  ARLEN,
  input  [2:0]  ARSIZE,
  input  [1:0]  ARBURST,
  input         ARVALID,
  output reg        ARREADY,
  output reg [ID_WIDTH-1:0] RID,
  output reg [31:0] RDATA,
  output reg [1:0]  RRESP,
  output reg        RLAST,
  output reg        RVALID,
  input         RREADY,
  input  [ID_WIDTH-1:0] AWID,
  input  [31:0] AWADDR,
  input  [7:0]  AWLEN,
  input  [2:0]  AWSIZE,
  input  [1:0]  AWBURST,
  input         AWVALID,
  output reg        AWREADY,
  input  [ID_WIDTH-1:0] WID,
  input  [31:0] WDATA,
  input  [3:0]  WSTRB,
  input         WLAST,
  input         WVALID,
  output reg        WREADY,
  output reg [ID_WIDTH-1:0] BID,
  output reg [1:0]  BRESP,
  output reg        BVALID,
  input         BREADY
);

  reg [7:0] mem [0:4095];
  integer i;

  initial begin
    ARREADY = 1'b0;
    RVALID = 1'b0;
    RLAST = 1'b0;
    AWREADY = 1'b0;
    WREADY = 1'b0;
    BVALID = 1'b0;
    for (i = 0; i < 4096; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = INIT_WORD0[7:0];
    mem[1] = INIT_WORD0[15:8];
    mem[2] = INIT_WORD0[23:16];
    mem[3] = INIT_WORD0[31:24];
    mem[16] = INIT_WORD1[7:0];
    mem[17] = INIT_WORD1[15:8];
    mem[18] = INIT_WORD1[23:16];
    mem[19] = INIT_WORD1[31:24];
  end

  always @(posedge ACLK) begin
    ARREADY <= 1'b0;
    AWREADY <= 1'b0;
    WREADY <= 1'b0;
    if (ARVALID) begin
      ARREADY <= 1'b1;
      RID <= ARID;
      RDATA <= {mem[ARADDR - BASE + 3], mem[ARADDR - BASE + 2],
                mem[ARADDR - BASE + 1], mem[ARADDR - BASE + 0]};
      RRESP <= 2'b00;
      RLAST <= 1'b1;
      RVALID <= 1'b1;
    end else if (RVALID && RREADY) begin
      RVALID <= 1'b0;
      RLAST <= 1'b0;
    end
    if (AWVALID) AWREADY <= 1'b1;
    if (WVALID && WLAST) begin
      WREADY <= 1'b1;
      if (WSTRB[0]) mem[AWADDR - BASE + 0] <= WDATA[7:0];
      if (WSTRB[1]) mem[AWADDR - BASE + 1] <= WDATA[15:8];
      if (WSTRB[2]) mem[AWADDR - BASE + 2] <= WDATA[23:16];
      if (WSTRB[3]) mem[AWADDR - BASE + 3] <= WDATA[31:24];
      BID <= AWID;
      BRESP <= 2'b00;
      BVALID <= 1'b1;
    end else if (BVALID && BREADY)
      BVALID <= 1'b0;
  end

endmodule