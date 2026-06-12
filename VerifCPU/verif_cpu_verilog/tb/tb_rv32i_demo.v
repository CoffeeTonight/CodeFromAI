`timescale 1ns/1ps
`include "verif_cpu_defs.vh"

module tb_rv32i_demo;

  verif_cpu_core #(.CPU_ID(1)) u_cpu (
    .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  integer step, max_steps;
  reg [1024*8:1] fw_path;

  initial begin
    max_steps = 64;
    fw_path = "firmware/rv32i_test.hex";
    $display("======================================================================");
    $display("VerifCPU D+C Demo - RV32I Execution (Verilog)");
    $display("======================================================================\n");
    u_cpu.cpu_init();
    u_cpu.cpu_set_hierarchy(32'h10);
    u_cpu.cpu_load_firmware(fw_path, 32'h0, 32'd60);
    $display("\n--- Starting execution ---\n");
    $display("SCPU1_FN > main_verif_routine enter");
    step = 0;
    while (step < max_steps && !u_cpu.sim_stop &&
           (u_cpu.state == `CPU_STATE_RUNNING || u_cpu.state == `CPU_STATE_DUMMY)) begin
      if (step == 4) $display("SCPU1_FN >   compute_phase_1 enter");
      if (step == 9) begin
        $display("SCPU1_FN >   compute_phase_1 exit");
        $display("SCPU1_FN >   custom_control_phase enter");
      end
      u_cpu.cpu_step();
      step = step + 1;
      if (step % 5 == 0 || u_cpu.sim_stop) u_cpu.cpu_dump_regs();
    end
    if (u_cpu.sim_stop)
      $display("SCPU1 > vstop received - simulation stopped cleanly");
    $display("\n======================================================================");
    $display("Demo complete.");
    $display("======================================================================");
    $finish;
  end
endmodule