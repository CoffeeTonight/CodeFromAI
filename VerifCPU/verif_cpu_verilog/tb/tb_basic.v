`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_sim_watchdog.vh"
`include "verif_tb_check.vh"

module tb_basic;

  localparam integer TB_EXPECTED_PASS = 6;
  localparam integer IRQ_W = 8;  // example: instance can set NUM_IRQ

  `VERIF_SIM_WATCHDOG_NS

  reg [IRQ_W-1:0] cpu1_irq;
  reg [31:0]      cpu2_irq;  // default NUM_IRQ=32

  verif_cpu_core #(.CPU_ID(1), .NUM_IRQ(IRQ_W)) u_cpu1 (
    .irq(cpu1_irq), .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  verif_cpu_core #(.CPU_ID(2)) u_cpu2 (
    .irq(cpu2_irq), .final_pc(), .total_steps(), .sim_stop(),
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
    cpu1_irq = {IRQ_W{1'b0}};
    cpu2_irq = 32'b0;
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

    // IRQ: change-detect + empty zero-cycle handler (no total_steps burn)
    $display("\n--- IRQ change detect (NUM_IRQ=%0d on cpu1) ---", IRQ_W);
    #1;
    steps_before_irq = u_cpu1.total_steps;
    cpu1_irq[3] = 1'b1;  // assert bit 3
    #1;
    cpu1_irq[3] = 1'b0;  // deassert bit 3
    #1;
    cpu1_irq[0] = 1'b1;
    cpu1_irq[7] = 1'b1;  // multi-bit edge in one assign? sequential
    #1;
    check_eq("irq zero-cycle (steps unchanged)", u_cpu1.total_steps == steps_before_irq);
    check_eq("irq NUM_IRQ param", u_cpu1.NUM_IRQ == IRQ_W);

    $display("\nChecklist: %0d passed / %0d failed", check_pass, check_fail);
    if (check_pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_basic: pass=%0d expected %0d", check_pass, TB_EXPECTED_PASS);
    if (check_fail != 0) $fatal(1, "tb_basic FAILED");
    $display("=== Demo Finished — PASS ===");
    $finish;
  end
endmodule