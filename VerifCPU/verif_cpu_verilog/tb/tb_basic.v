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

  initial begin
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
    $display("\n=== Demo Finished ===");
    $finish;
  end
endmodule