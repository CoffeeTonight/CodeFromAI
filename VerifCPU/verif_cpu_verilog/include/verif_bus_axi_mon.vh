// Icarus-safe AXI handshake monitors (always-block style, no $past).
// Include inside a module that has CLK/RSTn and the watched VALID/READY nets.
//
// Usage (TAG is an identifier used in reg names and messages):
//   `VERIF_BUS_AXI_MON_HS(clk, aresetn, arvalid, arready, AR)
`ifndef VERIF_BUS_AXI_MON_VH
`define VERIF_BUS_AXI_MON_VH

// If VALID was high and READY low last cycle, VALID must still be high now.
`define VERIF_BUS_AXI_MON_HS(CLK, RSTn, VALID, READY, TAG) \
  reg _mon_hs_``TAG``_v; \
  reg _mon_hs_``TAG``_r; \
  always @(posedge CLK or negedge RSTn) begin \
    if (!RSTn) begin \
      _mon_hs_``TAG``_v <= 1'b0; \
      _mon_hs_``TAG``_r <= 1'b0; \
    end else begin \
      if (_mon_hs_``TAG``_v && !_mon_hs_``TAG``_r && !VALID) \
        $error("[axi_mon] %s: VALID dropped before READY", `"TAG`"); \
      _mon_hs_``TAG``_v <= VALID; \
      _mon_hs_``TAG``_r <= READY; \
    end \
  end

`define VERIF_BUS_AXI_MON_VALID_KNOWN(CLK, RSTn, VALID, TAG) \
  always @(posedge CLK) begin \
    if (RSTn === 1'b1) begin \
      if (VALID === 1'bx || VALID === 1'bz) \
        $error("[axi_mon] %s: VALID is X/Z", `"TAG`"); \
    end \
  end

`endif
