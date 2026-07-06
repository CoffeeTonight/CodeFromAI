// Auto-generated shell — SSOT body in include/soc_integration_example_gen.vh
// YAML: firmware/campaign/soc_integration_ports.yaml  |  Run: make soc-integration

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"

module soc_integration_example;

  reg soc_clk = 0;
  reg soc_rstn = 0;
  always #5 soc_clk = ~soc_clk;

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count()
  );

  initial begin
    $dumpfile("sim_build/soc_integration_example.vcd");
    $dumpvars(0, soc_integration_example);
  end

  `include "soc_integration_example_gen.vh"

endmodule
