// AMBA bus connect macros — VerifCPU bridge ↔ SoC interconnect prefix
`ifndef VERIF_AMBA_CONNECT_MACROS_VH
`define VERIF_AMBA_CONNECT_MACROS_VH

// APB2 — optional PREADY stretch; no PSLVERR/PSTRB on master
`define CONNECT_APB2(SOC_PREF, MST) \
  assign SOC_PREF``_PADDR   = MST.PADDR; \
  assign SOC_PREF``_PSEL    = MST.PSEL; \
  assign SOC_PREF``_PENABLE = MST.PENABLE; \
  assign SOC_PREF``_PWRITE  = MST.PWRITE; \
  assign SOC_PREF``_PWDATA  = MST.PWDATA; \
  assign MST.PRDATA  = SOC_PREF``_PRDATA; \
  assign MST.PREADY  = SOC_PREF``_PREADY

// APB3
`define CONNECT_APB3(SOC_PREF, MST) \
  assign SOC_PREF``_PADDR   = MST.PADDR; \
  assign SOC_PREF``_PSEL    = MST.PSEL; \
  assign SOC_PREF``_PENABLE = MST.PENABLE; \
  assign SOC_PREF``_PWRITE  = MST.PWRITE; \
  assign SOC_PREF``_PWDATA  = MST.PWDATA; \
  assign SOC_PREF``_PSTRB   = MST.PSTRB; \
  assign MST.PRDATA  = SOC_PREF``_PRDATA; \
  assign MST.PREADY  = SOC_PREF``_PREADY; \
  assign MST.PSLVERR = SOC_PREF``_PSLVERR

// APB4 — + PPROT
`define CONNECT_APB4(SOC_PREF, MST) \
  `CONNECT_APB3(SOC_PREF, MST); \
  assign SOC_PREF``_PPROT   = MST.PPROT

// APB5 — + PWAKEUP
`define CONNECT_APB5(SOC_PREF, MST) \
  `CONNECT_APB4(SOC_PREF, MST); \
  assign SOC_PREF``_PWAKEUP = MST.PWAKEUP

// AHB-Lite — HREADY is slave→master (SOC HREADYOUT); master does not drive HREADY
`define CONNECT_AHB_LITE(SOC_PREF, MST) \
  assign SOC_PREF``_HADDR    = MST.HADDR; \
  assign SOC_PREF``_HSIZE    = MST.HSIZE; \
  assign SOC_PREF``_HTRANS   = MST.HTRANS; \
  assign SOC_PREF``_HWRITE   = MST.HWRITE; \
  assign SOC_PREF``_HWDATA   = MST.HWDATA; \
  assign SOC_PREF``_HREADY   = 1'b1; \
  assign MST.HRDATA    = SOC_PREF``_HRDATA; \
  assign MST.HREADY    = SOC_PREF``_HREADYOUT; \
  assign MST.HRESP     = SOC_PREF``_HRESP

// AHB5-Lite — + security / exclusive
`define CONNECT_AHB5_LITE(SOC_PREF, MST) \
  `CONNECT_AHB_LITE(SOC_PREF, MST); \
  assign SOC_PREF``_HNONSEC  = MST.HNONSEC; \
  assign SOC_PREF``_HEXCL    = MST.HEXCL; \
  assign MST.HEXOK     = SOC_PREF``_HEXOK

// AHB full (single-master behavioral) — + burst / prot
`define CONNECT_AHB(SOC_PREF, MST) \
  `CONNECT_AHB5_LITE(SOC_PREF, MST); \
  assign SOC_PREF``_HBURST   = MST.HBURST; \
  assign SOC_PREF``_HPROT    = MST.HPROT; \
  assign SOC_PREF``_HMASTLOCK = MST.HMASTLOCK

// AXI4-Lite
`define CONNECT_AXI_LITE(SOC_PREF, MST) \
  assign SOC_PREF``_arvalid = MST.ARVALID; \
  assign SOC_PREF``_araddr  = MST.ARADDR; \
  assign SOC_PREF``_arsize  = MST.ARSIZE; \
  assign MST.ARREADY = SOC_PREF``_arready; \
  assign MST.RVALID  = SOC_PREF``_rvalid; \
  assign MST.RDATA   = SOC_PREF``_rdata; \
  assign MST.RRESP   = SOC_PREF``_rresp; \
  assign MST.RREADY  = SOC_PREF``_rready; \
  assign SOC_PREF``_awvalid = MST.AWVALID; \
  assign SOC_PREF``_awaddr  = MST.AWADDR; \
  assign SOC_PREF``_awsize  = MST.AWSIZE; \
  assign MST.AWREADY = SOC_PREF``_awready; \
  assign SOC_PREF``_wvalid  = MST.WVALID; \
  assign SOC_PREF``_wdata   = MST.WDATA; \
  assign SOC_PREF``_wstrb   = MST.WSTRB; \
  assign MST.WREADY  = SOC_PREF``_wready; \
  assign MST.BVALID  = SOC_PREF``_bvalid; \
  assign MST.BREADY  = SOC_PREF``_bready; \
  assign MST.BRESP   = SOC_PREF``_bresp

// AXI3 full — single-beat capable master (ID + burst + WID)
`define CONNECT_AXI3FULL(SOC_PREF, MST) \
  assign SOC_PREF``_arid    = MST.ARID; \
  assign SOC_PREF``_araddr  = MST.ARADDR; \
  assign SOC_PREF``_arlen   = MST.ARLEN; \
  assign SOC_PREF``_arsize  = MST.ARSIZE; \
  assign SOC_PREF``_arburst = MST.ARBURST; \
  assign SOC_PREF``_arprot  = MST.ARPROT; \
  assign SOC_PREF``_arvalid = MST.ARVALID; \
  assign MST.ARREADY = SOC_PREF``_arready; \
  assign MST.RID     = SOC_PREF``_rid; \
  assign MST.RDATA   = SOC_PREF``_rdata; \
  assign MST.RRESP   = SOC_PREF``_rresp; \
  assign MST.RLAST   = SOC_PREF``_rlast; \
  assign MST.RVALID  = SOC_PREF``_rvalid; \
  assign MST.RREADY  = SOC_PREF``_rready; \
  assign SOC_PREF``_awid    = MST.AWID; \
  assign SOC_PREF``_awaddr  = MST.AWADDR; \
  assign SOC_PREF``_awlen   = MST.AWLEN; \
  assign SOC_PREF``_awsize  = MST.AWSIZE; \
  assign SOC_PREF``_awburst = MST.AWBURST; \
  assign SOC_PREF``_awprot  = MST.AWPROT; \
  assign SOC_PREF``_awvalid = MST.AWVALID; \
  assign MST.AWREADY = SOC_PREF``_awready; \
  assign SOC_PREF``_wid     = MST.WID; \
  assign SOC_PREF``_wdata   = MST.WDATA; \
  assign SOC_PREF``_wstrb   = MST.WSTRB; \
  assign SOC_PREF``_wlast   = MST.WLAST; \
  assign SOC_PREF``_wvalid  = MST.WVALID; \
  assign MST.WREADY  = SOC_PREF``_wready; \
  assign MST.BID     = SOC_PREF``_bid; \
  assign MST.BRESP   = SOC_PREF``_bresp; \
  assign MST.BVALID  = SOC_PREF``_bvalid; \
  assign MST.BREADY  = SOC_PREF``_bready

// AXI4 full — no WID; + QoS/Region optional tied in master
`define CONNECT_AXI4FULL(SOC_PREF, MST) \
  assign SOC_PREF``_arid    = MST.ARID; \
  assign SOC_PREF``_araddr  = MST.ARADDR; \
  assign SOC_PREF``_arlen   = MST.ARLEN; \
  assign SOC_PREF``_arsize  = MST.ARSIZE; \
  assign SOC_PREF``_arburst = MST.ARBURST; \
  assign SOC_PREF``_arqos   = MST.ARQOS; \
  assign SOC_PREF``_arregion = MST.ARREGION; \
  assign SOC_PREF``_arprot  = MST.ARPROT; \
  assign SOC_PREF``_arvalid = MST.ARVALID; \
  assign MST.ARREADY = SOC_PREF``_arready; \
  assign MST.RID     = SOC_PREF``_rid; \
  assign MST.RDATA   = SOC_PREF``_rdata; \
  assign MST.RRESP   = SOC_PREF``_rresp; \
  assign MST.RLAST   = SOC_PREF``_rlast; \
  assign MST.RVALID  = SOC_PREF``_rvalid; \
  assign MST.RREADY  = SOC_PREF``_rready; \
  assign SOC_PREF``_awid    = MST.AWID; \
  assign SOC_PREF``_awaddr  = MST.AWADDR; \
  assign SOC_PREF``_awlen   = MST.AWLEN; \
  assign SOC_PREF``_awsize  = MST.AWSIZE; \
  assign SOC_PREF``_awburst = MST.AWBURST; \
  assign SOC_PREF``_awqos   = MST.AWQOS; \
  assign SOC_PREF``_awregion = MST.AWREGION; \
  assign SOC_PREF``_awprot  = MST.AWPROT; \
  assign SOC_PREF``_awvalid = MST.AWVALID; \
  assign MST.AWREADY = SOC_PREF``_awready; \
  assign SOC_PREF``_wdata   = MST.WDATA; \
  assign SOC_PREF``_wstrb   = MST.WSTRB; \
  assign SOC_PREF``_wlast   = MST.WLAST; \
  assign SOC_PREF``_wvalid  = MST.WVALID; \
  assign MST.WREADY  = SOC_PREF``_wready; \
  assign MST.BID     = SOC_PREF``_bid; \
  assign MST.BRESP   = SOC_PREF``_bresp; \
  assign MST.BVALID  = SOC_PREF``_bvalid; \
  assign MST.BREADY  = SOC_PREF``_bready

// AXI5 full — + ATOP on AW
`define CONNECT_AXI5FULL(SOC_PREF, MST) \
  `CONNECT_AXI4FULL(SOC_PREF, MST); \
  assign SOC_PREF``_awatop  = MST.AWATOP

`endif