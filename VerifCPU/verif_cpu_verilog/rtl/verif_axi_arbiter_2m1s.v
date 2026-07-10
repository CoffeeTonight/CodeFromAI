// Behavioral 2-master / 1-slave AXI4 arbiter (round-robin AR/AW, ID-based R/B demux)
`timescale 1ns/1ps

module verif_axi_arbiter_2m1s #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int ID_WIDTH = 4,
  // M1 IDs must set this bit (e.g. ID_BASE=8); M0 uses lower IDs for multi-outstanding
  parameter int M1_ID_TAG_BIT = 3
)(
  input         ACLK,
  input         ARESETn,

  // Master 0 (ARID should be 0)
  input  [ID_WIDTH-1:0]   M0_ARID,
  input  [ADDR_WIDTH-1:0] M0_ARADDR,
  input  [7:0]            M0_ARLEN,
  input  [2:0]            M0_ARSIZE,
  input  [1:0]            M0_ARBURST,
  input                   M0_ARLOCK,
  input                   M0_ARVALID,
  output                  M0_ARREADY,

  input  [ID_WIDTH-1:0]   M0_AWID,
  input  [ADDR_WIDTH-1:0] M0_AWADDR,
  input  [7:0]            M0_AWLEN,
  input  [2:0]            M0_AWSIZE,
  input  [1:0]            M0_AWBURST,
  input                   M0_AWLOCK,
  input  [5:0]            M0_AWATOP,
  input                   M0_AWVALID,
  output                  M0_AWREADY,

  input  [DATA_WIDTH-1:0] M0_WDATA,
  input  [DATA_WIDTH/8-1:0] M0_WSTRB,
  input                   M0_WLAST,
  input                   M0_WVALID,
  output                  M0_WREADY,

  output [ID_WIDTH-1:0]   M0_BID,
  output [1:0]            M0_BRESP,
  output                  M0_BVALID,
  input                   M0_BREADY,

  output [ID_WIDTH-1:0]   M0_RID,
  output [DATA_WIDTH-1:0] M0_RDATA,
  output [1:0]            M0_RRESP,
  output                  M0_RLAST,
  output                  M0_RVALID,
  input                   M0_RREADY,

  // Master 1 (ARID[ M1_ID_TAG_BIT ] must be 1, e.g. ID_BASE=8)
  input  [ID_WIDTH-1:0]   M1_ARID,
  input  [ADDR_WIDTH-1:0] M1_ARADDR,
  input  [7:0]            M1_ARLEN,
  input  [2:0]            M1_ARSIZE,
  input  [1:0]            M1_ARBURST,
  input                   M1_ARLOCK,
  input                   M1_ARVALID,
  output                  M1_ARREADY,

  input  [ID_WIDTH-1:0]   M1_AWID,
  input  [ADDR_WIDTH-1:0] M1_AWADDR,
  input  [7:0]            M1_AWLEN,
  input  [2:0]            M1_AWSIZE,
  input  [1:0]            M1_AWBURST,
  input                   M1_AWLOCK,
  input  [5:0]            M1_AWATOP,
  input                   M1_AWVALID,
  output                  M1_AWREADY,

  input  [DATA_WIDTH-1:0] M1_WDATA,
  input  [DATA_WIDTH/8-1:0] M1_WSTRB,
  input                   M1_WLAST,
  input                   M1_WVALID,
  output                  M1_WREADY,

  output [ID_WIDTH-1:0]   M1_BID,
  output [1:0]            M1_BRESP,
  output                  M1_BVALID,
  input                   M1_BREADY,

  output [ID_WIDTH-1:0]   M1_RID,
  output [DATA_WIDTH-1:0] M1_RDATA,
  output [1:0]            M1_RRESP,
  output                  M1_RLAST,
  output                  M1_RVALID,
  input                   M1_RREADY,

  // Slave
  output [ID_WIDTH-1:0]   S_ARID,
  output [ADDR_WIDTH-1:0] S_ARADDR,
  output [7:0]            S_ARLEN,
  output [2:0]            S_ARSIZE,
  output [1:0]            S_ARBURST,
  output                  S_ARLOCK,
  output                  S_ARVALID,
  input                   S_ARREADY,

  output [ID_WIDTH-1:0]   S_AWID,
  output [ADDR_WIDTH-1:0] S_AWADDR,
  output [7:0]            S_AWLEN,
  output [2:0]            S_AWSIZE,
  output [1:0]            S_AWBURST,
  output                  S_AWLOCK,
  output [5:0]            S_AWATOP,
  output                  S_AWVALID,
  input                   S_AWREADY,

  output [DATA_WIDTH-1:0] S_WDATA,
  output [DATA_WIDTH/8-1:0] S_WSTRB,
  output                  S_WLAST,
  output                  S_WVALID,
  input                   S_WREADY,

  input  [ID_WIDTH-1:0]   S_BID,
  input  [1:0]            S_BRESP,
  input                   S_BVALID,
  output                  S_BREADY,

  input  [ID_WIDTH-1:0]   S_RID,
  input  [DATA_WIDTH-1:0] S_RDATA,
  input  [1:0]            S_RRESP,
  input                   S_RLAST,
  input                   S_RVALID,
  output                  S_RREADY
);

  reg        ar_grant;
  reg        aw_grant;
  reg        w_master;     // 0=M0, 1=M1 — W follows last AW winner
  reg        aw_m0_latched;
  reg        aw_m1_latched;
  reg        m0_ar_locked;
  reg        m1_ar_locked;
  reg        m0_aw_locked;
  reg        m1_aw_locked;

  wire       ar_pick_m0;
  wire       ar_pick_m1;
  wire       ar_hs;
  wire       aw_pick_m0;
  wire       aw_pick_m1;
  wire       aw_hs;
  wire       r_for_m0;
  wire       r_for_m1;
  wire       b_for_m0;
  wire       b_for_m1;

  // Lock-aware: locked master holds AR/AW grant until burst completes (RLAST/WLAST)
  assign ar_pick_m0 = M0_ARVALID &&
    (m0_ar_locked || (!m1_ar_locked && (!M1_ARVALID || !ar_grant)));
  assign ar_pick_m1 = M1_ARVALID &&
    (m1_ar_locked || (!m0_ar_locked && (!M0_ARVALID || ar_grant)));
  assign ar_hs = S_ARVALID && S_ARREADY;

  assign aw_pick_m0 = M0_AWVALID &&
    (m0_aw_locked || (!m1_aw_locked && (!M1_AWVALID || !aw_grant)));
  assign aw_pick_m1 = M1_AWVALID &&
    (m1_aw_locked || (!m0_aw_locked && (!M0_AWVALID || aw_grant)));
  assign aw_hs = S_AWVALID && S_AWREADY;

  assign S_ARVALID = ar_pick_m0 || ar_pick_m1;
  assign S_ARID    = ar_pick_m1 ? M1_ARID : M0_ARID;
  assign S_ARADDR  = ar_pick_m1 ? M1_ARADDR : M0_ARADDR;
  assign S_ARLEN   = ar_pick_m1 ? M1_ARLEN : M0_ARLEN;
  assign S_ARSIZE  = ar_pick_m1 ? M1_ARSIZE : M0_ARSIZE;
  assign S_ARBURST = ar_pick_m1 ? M1_ARBURST : M0_ARBURST;
  assign S_ARLOCK  = ar_pick_m1 ? M1_ARLOCK : M0_ARLOCK;
  assign M0_ARREADY = ar_pick_m0 && S_ARREADY;
  assign M1_ARREADY = ar_pick_m1 && S_ARREADY;

  assign S_AWVALID = aw_pick_m0 || aw_pick_m1;
  assign S_AWID    = aw_pick_m1 ? M1_AWID : M0_AWID;
  assign S_AWADDR  = aw_pick_m1 ? M1_AWADDR : M0_AWADDR;
  assign S_AWLEN   = aw_pick_m1 ? M1_AWLEN : M0_AWLEN;
  assign S_AWSIZE  = aw_pick_m1 ? M1_AWSIZE : M0_AWSIZE;
  assign S_AWBURST = aw_pick_m1 ? M1_AWBURST : M0_AWBURST;
  assign S_AWLOCK  = aw_pick_m1 ? M1_AWLOCK : M0_AWLOCK;
  assign S_AWATOP  = aw_pick_m1 ? M1_AWATOP : M0_AWATOP;
  assign M0_AWREADY = aw_pick_m0 && S_AWREADY;
  assign M1_AWREADY = aw_pick_m1 && S_AWREADY;

  assign S_WVALID = w_master ? M1_WVALID : M0_WVALID;
  assign S_WDATA  = w_master ? M1_WDATA : M0_WDATA;
  assign S_WSTRB  = w_master ? M1_WSTRB : M0_WSTRB;
  assign S_WLAST  = w_master ? M1_WLAST : M0_WLAST;
  assign M0_WREADY = (!w_master && aw_m0_latched) ? S_WREADY : 1'b0;
  assign M1_WREADY = ( w_master && aw_m1_latched) ? S_WREADY : 1'b0;

  assign r_for_m0 = S_RVALID && !S_RID[M1_ID_TAG_BIT];
  assign r_for_m1 = S_RVALID &&  S_RID[M1_ID_TAG_BIT];
  assign M0_RID    = S_RID;
  assign M0_RDATA  = S_RDATA;
  assign M0_RRESP  = S_RRESP;
  assign M0_RLAST  = S_RLAST;
  assign M0_RVALID = r_for_m0;
  assign M1_RID    = S_RID;
  assign M1_RDATA  = S_RDATA;
  assign M1_RRESP  = S_RRESP;
  assign M1_RLAST  = S_RLAST;
  assign M1_RVALID = r_for_m1;
  assign S_RREADY  = r_for_m0 ? M0_RREADY : (r_for_m1 ? M1_RREADY : 1'b0);

  assign b_for_m0 = S_BVALID && !S_BID[M1_ID_TAG_BIT];
  assign b_for_m1 = S_BVALID &&  S_BID[M1_ID_TAG_BIT];
  assign M0_BID    = S_BID;
  assign M0_BRESP  = S_BRESP;
  assign M0_BVALID = b_for_m0;
  assign M1_BID    = S_BID;
  assign M1_BRESP  = S_BRESP;
  assign M1_BVALID = b_for_m1;
  assign S_BREADY  = b_for_m0 ? M0_BREADY : (b_for_m1 ? M1_BREADY : 1'b0);

  always @(posedge ACLK or negedge ARESETn) begin
    if (!ARESETn) begin
      ar_grant <= 1'b0;
      aw_grant <= 1'b0;
      w_master <= 1'b0;
      aw_m0_latched <= 1'b0;
      aw_m1_latched <= 1'b0;
      m0_ar_locked <= 1'b0;
      m1_ar_locked <= 1'b0;
      m0_aw_locked <= 1'b0;
      m1_aw_locked <= 1'b0;
    end else begin
      if (ar_hs) begin
        if (ar_pick_m1) begin
          ar_grant <= 1'b0;
          if (M1_ARLOCK)
            m1_ar_locked <= 1'b1;
        end else if (ar_pick_m0) begin
          ar_grant <= 1'b1;
          if (M0_ARLOCK)
            m0_ar_locked <= 1'b1;
        end
      end
      if (M0_RVALID && M0_RREADY && M0_RLAST)
        m0_ar_locked <= 1'b0;
      if (M1_RVALID && M1_RREADY && M1_RLAST)
        m1_ar_locked <= 1'b0;
      if (aw_hs) begin
        aw_m0_latched <= 1'b0;
        aw_m1_latched <= 1'b0;
        if (aw_pick_m1) begin
          aw_grant <= 1'b0;
          w_master <= 1'b1;
          aw_m1_latched <= 1'b1;
          if (M1_AWLOCK)
            m1_aw_locked <= 1'b1;
        end else if (aw_pick_m0) begin
          aw_grant <= 1'b1;
          w_master <= 1'b0;
          aw_m0_latched <= 1'b1;
          if (M0_AWLOCK)
            m0_aw_locked <= 1'b1;
        end
      end
      if (S_WVALID && S_WREADY && S_WLAST) begin
        aw_m0_latched <= 1'b0;
        aw_m1_latched <= 1'b0;
        if (w_master)
          m1_aw_locked <= 1'b0;
        else
          m0_aw_locked <= 1'b0;
      end
    end
  end

endmodule