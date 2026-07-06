// Scale integration TB — flat g_slv[0..N-1] from manifest BUS_LAYOUT + active campaign subset
// Fabric (wires, stubs, cells, CONNECT) in tb_soc_manifest_scale_gen.vh — edit YAML, not this file.

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"
`include "campaign_params.vh"
`include "campaign_soc_platform.vh"
`include "campaign_manifest.vh"
`include "icode_map.vh"
`include "icode_bind.vh"
`include "verif_soc_bus_connect.vh"
`include "tb_soc_manifest_scale_defs.vh"
`include "tb_soc_manifest_defs.vh"

module tb_soc_manifest_scale;

  localparam FW_SIZE       = 32'h2000;
  localparam MAX_WAIT      = 32'd50000;
  localparam ICODE_POOL_SZ = `SOC_MANIFEST_ICODE_POOL_BYTES;

  reg soc_clk = 0;
  reg soc_rstn = 0;
  always #5 soc_clk = ~soc_clk;

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;
  wire [31:0] orch_reset_count;

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count(orch_reset_count)
  );

  verif_cpu_unified_pool #(.MEM_WORDS(32'h80000)) u_pool ();

  `CAMPAIGN_MASTER_INSTANCE

  `include "tb_soc_manifest_scale_gen.vh"
  `include "tb_soc_manifest_decode.vh"

  integer pass, fail;
  reg [31:0] rdata, orch_rst_before, total_pass, total_fail;
  reg [1:0]  rresp, rport;
  reg        icode_exec_ok, init_ok;
  integer    poll;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  task manifest_soc_run_init;
    reg [31:0] rd;
    reg [1:0] r, p;
    begin
      g_slv0.u_bus.u_cpu.sim_stop = 1;
      g_slv1.u_bus.u_cpu.sim_stop = 1;
      g_slv2.u_bus.u_cpu.sim_stop = 1;
      g_slv0.u_bus.u_cpu.request_sim_stop = 0;
      g_slv1.u_bus.u_cpu.request_sim_stop = 0;
      g_slv2.u_bus.u_cpu.request_sim_stop = 0;
      repeat (2) @(posedge soc_clk);
      `SOC_MANIFEST_INIT_STEPS
    end
  endtask

  task manifest_master_wait_init_done;
    output ok;
    reg [31:0] rd;
    reg [1:0] rr;
    reg [1:0] rp;
    begin
      ok = 0;
      if (u_mstr.INIT_DONE_ADDR == 32'h0) begin
        ok = 1;
      end else begin
        for (poll = 0; poll < u_mstr.INIT_DONE_POLL_MAX; poll = poll + 1) begin
          manifest_decode_read(u_mstr.INIT_DONE_ADDR, 3'd4, rd, rr, rp);
          if (rr == 2'd0 && u_mstr.init_done_met(rd)) begin
            ok = 1;
            poll = u_mstr.INIT_DONE_POLL_MAX;
          end
        end
      end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    soc_rstn = 1'b0;
    repeat (4) @(posedge soc_clk);
    soc_rstn = 1'b1;
    repeat (2) @(posedge soc_clk);

    $dumpfile("sim_build/tb_soc_manifest_scale.vcd");
    $dumpvars(0, tb_soc_manifest_scale);

    $display("========================================================================");
    $display("tb_soc_manifest_scale: %0d wired cells (max gi %0d)",
             `SOC_MANIFEST_SCALE_NUM_WIRED, `SOC_MANIFEST_SCALE_MAX_GI);
    $display("========================================================================");

    check("Scale wired count", `SOC_MANIFEST_SCALE_NUM_WIRED >= 3);
    check("Scale max gi matches wired cell count",
          `SOC_MANIFEST_SCALE_MAX_GI == `SOC_MANIFEST_SCALE_NUM_WIRED);
    check("Scale last g_slv cell present", `SOC_MANIFEST_SCALE_LAST_CELL_OK);

    `SOC_MANIFEST_LOAD_POOL
    check("Pool loaded", 1);

    `SOC_MANIFEST_SETUP_CPUS

    $display("\n[1] Phase A — active subset on flat %0d-cell fabric",
             `SOC_MANIFEST_SCALE_NUM_WIRED);
    u_orch.phase_release(`PHASE_INIT, `SOC_MANIFEST_OFF_A);
    `SOC_MANIFEST_RUN_PHASE_A
    `SOC_MANIFEST_PHASE_A_CHECKS

    $display("\n[2] Phase B — master init_done + hints + collect");
    manifest_master_wait_init_done(init_ok);
    check("Master init_done poll", init_ok);
    `SOC_MANIFEST_RUN_PHASE_B
    check("Phase B multi-slots (2 per agent)", `SOC_MANIFEST_PHASE_B_SLOT_CHECK);

    $display("\n[3] Platform icode — RV32 exec + multi-slot verify");
    `SOC_MANIFEST_ICODE_RV32_EXEC
    `SOC_MANIFEST_ICODE_MAP_BUS_CHECKS
    `SOC_MANIFEST_ICODE_AGENT_ROUNDS
    `SOC_MANIFEST_ICODE_FINAL_CHECKS

    $display("");
    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "tb_soc_manifest_scale FAILED");
    $display("tb_soc_manifest_scale: PASS");
    $finish;
  end

endmodule