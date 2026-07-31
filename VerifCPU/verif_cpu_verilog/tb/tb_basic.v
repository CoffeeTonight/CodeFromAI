`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_sim_watchdog.vh"
`include "verif_tb_check.vh"

module tb_basic;

  localparam integer TB_EXPECTED_PASS = 13;
  localparam integer IRQ0_W = 8;
  localparam integer IRQ1_W = 4;

  `VERIF_SIM_WATCHDOG_NS

  reg [IRQ0_W-1:0] cpu1_irq0;
  reg [IRQ1_W-1:0] cpu1_irq1;
  reg [31:0]       cpu2_irq0;

  verif_cpu_core #(.CPU_ID(1), .NUM_IRQ0(IRQ0_W), .NUM_IRQ1(IRQ1_W)) u_cpu1 (
    .irq0(cpu1_irq0), .irq1(cpu1_irq1), .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  verif_cpu_core #(.CPU_ID(2)) u_cpu2 (
    .irq0(cpu2_irq0), .irq1(`VERIF_CPU_IRQ1_TIED_OFF), .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  integer check_pass, check_fail;
  reg [31:0] steps_before_irq;

  task check_eq;
    input [8*`VERIF_TB_CHECK_NAME_CHARS-1:0] name;
    input cond;
    begin
      if (cond) begin check_pass = check_pass + 1; $display("  [PASS] %0s", name); end
      else begin check_fail = check_fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    check_pass = 0;
    check_fail = 0;
    cpu1_irq0 = {IRQ0_W{1'b0}};
    cpu1_irq1 = {IRQ1_W{1'b0}};
    cpu2_irq0 = 32'b0;
    $dumpfile("sim_build/tb_basic.vcd");
    $dumpvars(0, tb_basic);
    $display("=== VerifCPU Basic Demo (Verilog) ===\n");
    u_cpu1.cpu_init();
    u_cpu2.cpu_init();
    u_cpu1.cpu_set_hierarchy(32'h10);
    u_cpu2.cpu_set_hierarchy(32'h20);
    u_cpu1.cpu_step(); u_cpu1.cpu_step(); u_cpu1.cpu_step();
    u_cpu2.cpu_step(); u_cpu2.cpu_step(); u_cpu2.cpu_step();
    $display("\n--- Console Control Simulation ---");
    u_cpu1.cpu_stall();
    u_cpu1.cpu_resume();
    u_cpu2.enter_dummy_mode();
    u_cpu2.exit_dummy_mode();
    check_eq("cpu1 stepped", u_cpu1.total_steps == 3);
    check_eq("cpu2 stepped", u_cpu2.total_steps == 3);
    check_eq("cpu1 running", u_cpu1.state == `CPU_STATE_RUNNING);
    check_eq("cpu2 running", u_cpu2.state == `CPU_STATE_RUNNING);

    // Dual-group IRQ: change-detect + zero-cycle handler (rise+fall each = 2 services)
    $display("\n--- IRQ grp0 (NUM_IRQ0=%0d) / grp1 (NUM_IRQ1=%0d) ---", IRQ0_W, IRQ1_W);
    #1;
    steps_before_irq = u_cpu1.total_steps;
    cpu1_irq0[3] = 1'b1;
    #1;
    check_eq("irq0 rise latched in prev", u_cpu1.irq0_prev[3] == 1'b1);
    cpu1_irq0[3] = 1'b0;
    #1;
    check_eq("irq0 fall latched in prev", u_cpu1.irq0_prev[3] == 1'b0);
    cpu1_irq1[1] = 1'b1;  // group 1 edge
    #1;
    check_eq("irq1 rise latched in prev", u_cpu1.irq1_prev[1] == 1'b1);
    cpu1_irq1[1] = 1'b0;
    #1;
    check_eq("irq1 fall latched in prev", u_cpu1.irq1_prev[1] == 1'b0);
    check_eq("irq zero-cycle (steps unchanged)", u_cpu1.total_steps == steps_before_irq);
    check_eq("irq NUM_IRQ0 param", u_cpu1.NUM_IRQ0 == IRQ0_W);
    check_eq("irq NUM_IRQ1 param", u_cpu1.NUM_IRQ1 == IRQ1_W);
    check_eq("irq0 service count (rise+fall)", u_cpu1.irq0_service_count == 2);
    check_eq("irq1 service count (rise+fall)", u_cpu1.irq1_service_count == 2);

    $display("\nChecklist: %0d passed / %0d failed", check_pass, check_fail);
    if (check_pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_basic: pass=%0d expected %0d", check_pass, TB_EXPECTED_PASS);
    if (check_fail != 0) $fatal(1, "tb_basic FAILED");
    $display("=== Demo Finished — PASS ===");
    $finish;
  end
endmodule
