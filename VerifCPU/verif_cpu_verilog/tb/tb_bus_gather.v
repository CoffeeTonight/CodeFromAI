`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_sim_watchdog.vh"
`include "verif_tb_check.vh"

// Smoke: bus store-gather on/off for consecutive word writes (long long style).
module tb_bus_gather;

  localparam integer TB_EXPECTED_PASS = 16;

  `VERIF_SIM_WATCHDOG_NS

  reg [31:0] irq0;
  verif_cpu_core #(.CPU_ID(1), .NUM_IRQ(32)) u_cpu (
    .irq(irq0), .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  integer check_pass, check_fail;
  integer flush_before, words_before, narrow_before;

  task check_eq;
    input [8*`VERIF_TB_CHECK_NAME_CHARS-1:0] name;
    input cond;
    begin
      if (cond) begin check_pass = check_pass + 1; $display("  [PASS] %0s", name); end
      else begin check_fail = check_fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    irq0 = 0;
    check_pass = 0;
    check_fail = 0;
    $dumpfile("sim_build/tb_bus_gather.vcd");
    $dumpvars(0, tb_bus_gather);
    $display("=== VerifCPU Bus Gather Smoke ===\n");

    u_cpu.cpu_init();
    u_cpu.cpu_set_hierarchy(32'h10);

    // --- OFF: no gather / no narrow ---
    flush_before = u_cpu.gather_flush_n;
    words_before = u_cpu.gather_words_out;
    narrow_before = u_cpu.gather_narrow_n;
    u_cpu.do_bus_write(32'h1000, 32'hA1A1A1A1, 3'd4);
    u_cpu.do_bus_write(32'h1004, 32'hB2B2B2B2, 3'd4);
    check_eq("off: no gather flush", u_cpu.gather_flush_n == flush_before);
    check_eq("off: no gather words", u_cpu.gather_words_out == words_before);
    check_eq("off: no narrow", u_cpu.gather_narrow_n == narrow_before);

    // --- ON(1): word store → 4× 1B narrow ---
    u_cpu.cpu_bus_gather_on(1);
    check_eq("on(1): width", u_cpu.gather_width == 5'd1);
    narrow_before = u_cpu.gather_narrow_n;
    u_cpu.do_bus_write(32'h1100, 32'hAABBCCDD, 3'd4);
    check_eq("on(1): 4 byte issues", u_cpu.gather_narrow_n == narrow_before + 4);

    // --- ON(8): two consecutive words → auto 8B gather flush ---
    u_cpu.cpu_bus_gather_on(8);
    check_eq("on(8): width", u_cpu.gather_width == 5'd8);
    flush_before = u_cpu.gather_flush_n;
    words_before = u_cpu.gather_words_out;
    u_cpu.do_bus_write(32'h2000, 32'h11111111, 3'd4);
    check_eq("on(8): pending after 1 word", u_cpu.gather_count == 3'd1);
    u_cpu.do_bus_write(32'h2004, 32'h22222222, 3'd4);
    check_eq("on(8): auto-flush 8B", u_cpu.gather_flush_n == flush_before + 1);
    check_eq("on(8): two words out", u_cpu.gather_words_out == words_before + 2);
    check_eq("on(8): buffer empty", u_cpu.gather_count == 3'd0);

    // --- gap ---
    flush_before = u_cpu.gather_flush_n;
    u_cpu.do_bus_write(32'h3000, 32'h33333333, 3'd4);
    u_cpu.do_bus_write(32'h3010, 32'h44444444, 3'd4);
    check_eq("gap: flushed pending", u_cpu.gather_flush_n == flush_before + 1);
    check_eq("gap: buffer empty", u_cpu.gather_count == 3'd0);

    // --- ON(16) ---
    u_cpu.cpu_bus_gather_on(16);
    check_eq("on(16): width", u_cpu.gather_width == 5'd16);
    flush_before = u_cpu.gather_flush_n;
    words_before = u_cpu.gather_words_out;
    u_cpu.do_bus_write(32'h4000, 32'h01010101, 3'd4);
    u_cpu.do_bus_write(32'h4004, 32'h02020202, 3'd4);
    check_eq("16B: still pending after 8B", u_cpu.gather_count == 3'd2);
    u_cpu.do_bus_write(32'h4008, 32'h03030303, 3'd4);
    u_cpu.do_bus_write(32'h400c, 32'h04040404, 3'd4);
    check_eq("16B: auto-flush", u_cpu.gather_flush_n == flush_before + 1);
    check_eq("16B: four words out", u_cpu.gather_words_out == words_before + 4);

    u_cpu.cpu_bus_gather_off();

    $display("\nChecklist: %0d passed / %0d failed", check_pass, check_fail);
    if (check_pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_bus_gather: pass=%0d expected %0d", check_pass, TB_EXPECTED_PASS);
    if (check_fail != 0) $fatal(1, "tb_bus_gather FAILED");
    $display("=== Bus Gather Smoke — PASS ===");
    $finish;
  end
endmodule
