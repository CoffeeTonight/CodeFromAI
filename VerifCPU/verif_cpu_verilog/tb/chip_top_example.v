// Customer chip_top reference — manifest-driven fabric (chip_top_example_gen.vh)
// make chip-top-example
// SSOT: soc_hierarchy*.yaml → gen_soc_bus_connect.py / make icodes

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"
`include "campaign_scale.vh"
`include "verif_soc_bus_connect.vh"

module chip_top_example;

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

  verif_cpu_unified_pool #(.MEM_WORDS(32'h1000)) u_pool ();

  `include "chip_top_example_gen.vh"
  `include "chip_top_decode.vh"

  integer pass, fail;
  reg [31:0] wdata, rdata;
  reg [1:0]  wresp, rresp, rport;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  task chip_bus_wr_rd;
    input [8*64:1] label;
    input [31:0]   addr;
    input [31:0]   pattern;
    begin
      chip_decode_write(addr, pattern, 3'd4, wresp, rport);
      check({label, " write OK"}, wresp == 2'd0);
      chip_decode_read(addr, 3'd4, rdata, rresp, rport);
      check({label, " read OK"}, rresp == 2'd0);
      check({label, " data match"}, rdata == pattern);
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    $dumpvars(0, chip_top_example);
    soc_rstn = 1'b0;
    repeat (4) @(posedge soc_clk);
    soc_rstn = 1'b1;
    repeat (2) @(posedge soc_clk);

    $display("========================================================================");
    $display("chip_top_example: orchestrator + agent + bridge bus R/W (%0d cells)", HIER_N);
    $display("========================================================================");

    u_orch.phase_release(`PHASE_INIT, 32'h0);

    `SOC_CHIP_TOP_BUS_TESTS
    `SOC_CHIP_TOP_RUN_PHASE_A
    `SOC_CHIP_TOP_AGENT_CHECKS

    $display("");
    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "chip_top_example FAILED");
    $display("chip_top_example: PASS");
    $finish;
  end

endmodule