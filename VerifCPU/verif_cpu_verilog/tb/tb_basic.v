`timescale 1ns/1ps
`include "verif_cpu_defs.vh"

module tb_basic;

  verif_cpu_core #(.CPU_ID(1)) u_cpu1 (
    .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  verif_cpu_core #(.CPU_ID(2)) u_cpu2 (
    .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  integer check_pass, check_fail;

  task check_eq;
    input [8*96:1] name;
    input cond;
    begin
      if (cond) begin check_pass = check_pass + 1; $display("  [PASS] %0s", name); end
      else begin check_fail = check_fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    check_pass = 0;
    check_fail = 0;
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
    $display("\nChecklist: %0d passed / %0d failed", check_pass, check_fail);
    if (check_fail != 0) $fatal(1, "tb_basic FAILED");
    $display("=== Demo Finished — PASS ===");
    $finish;
  end
endmodule