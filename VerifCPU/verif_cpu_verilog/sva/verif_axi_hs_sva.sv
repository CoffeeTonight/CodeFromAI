// Optional SystemVerilog Assertions for AXI handshake stability.
// Commercial tools (VCS / Xcelium): compile with +define+VERIF_BUS_SVA and bind.
// Icarus: not required — use include/verif_bus_axi_mon.vh + tb_axi_sva_smoke.v instead.
//
// Properties:
//   - VALID stays asserted until READY (no premature drop)
//   - VALID is known (not X/Z) after reset

`ifndef VERIF_AXI_HS_SVA_SV
`define VERIF_AXI_HS_SVA_SV

module verif_axi_hs_sva #(
  parameter string TAG = "AXI"
)(
  input logic clk,
  input logic rst_n,
  input logic valid,
  input logic ready
);

`ifdef VERIF_BUS_SVA
  // VALID must hold until handshake completes
  property p_valid_stable;
    @(posedge clk) disable iff (!rst_n)
      (valid && !ready) |=> valid;
  endproperty
  a_valid_stable: assert property (p_valid_stable)
    else $error("[sva] %0s: VALID dropped before READY", TAG);

  // VALID known after reset deassert
  property p_valid_known;
    @(posedge clk) disable iff (!rst_n)
      !$isunknown(valid);
  endproperty
  a_valid_known: assert property (p_valid_known)
    else $error("[sva] %0s: VALID is X/Z", TAG);

  // Cover: at least one handshake
  c_handshake: cover property (@(posedge clk) disable iff (!rst_n) (valid && ready));
`endif

endmodule

// Bind helper — instantiate against a master instance hierarchical nets, e.g.:
//   bind verif_axi_full_master verif_axi_hs_sva #(.TAG("AR")) u_sva_ar (
//     .clk(ACLK), .rst_n(ARESETn), .valid(ARVALID), .ready(ARREADY));
// Prefer TB-level instances (below in tb_axi_sva_smoke) for tool portability.

`endif
