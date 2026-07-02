// Full verification harness - mirrors demo_verification_harness.py

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"

module tb_verification_harness;

  verif_cpu_bus u_shared_bus ();
  verif_cpu_unified_pool u_pool ();

  verif_cpu_core #(.CPU_ID(1), .USE_SHARED_BUS(1), .USE_SHARED_POOL(1)) u_cpu1 (
    .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );
  verif_cpu_core #(.CPU_ID(2), .USE_SHARED_BUS(1), .USE_SHARED_POOL(1)) u_cpu2 (
    .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );
  verif_cpu_core #(.CPU_ID(3), .USE_SHARED_BUS(1), .USE_SHARED_POOL(1)) u_cpu3 (
    .final_pc(), .total_steps(), .sim_stop(),
    .assert_pass(), .assert_fail(), .bus_txn_count(),
    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()
  );

  reg [1024*8:1] log_dir;
  reg [1024*8:1] fw_path;
  reg [1024*8:1] vcd_path;
  reg [1024*8:1] rpt_json;
  reg [1024*8:1] rpt_md;
  integer step, max_steps;
  reg [31:0] rdata;
  integer rpt_fd;

  task console_help;
    begin
      $display("[Console] tb_verification_harness — call console_cmd(cid, cmd, a0, a1, a2)");
      u_cpu1.cpu_console_help();
    end
  endtask

  task console_cmd;
    input [3:0]    cid;
    input [8*32:1] cmd;
    input [31:0]   a0;
    input [31:0]   a1;
    input [31:0]   a2;
    begin
      if (cid == 0 || cid == 1) u_cpu1.cpu_console_dispatch(cmd, a0, a1, a2);
      if (cid == 0 || cid == 2) u_cpu2.cpu_console_dispatch(cmd, a0, a1, a2);
      if (cid == 0 || cid == 3) u_cpu3.cpu_console_dispatch(cmd, a0, a1, a2);
      if (cid > 4'd3)
        $display("[Console] unknown cpu_id=%0d (harness VCPUs 1..3)", cid);
    end
  endtask

  task setup_cpu;
    input [3:0] cid;
    input [8*64:1] role;
    input [31:0] pool_base;
    input [31:0] fw_size;
    input [31:0] wdt_to;
    input [31:0] hier;
    reg [1024*8:1] logpath;
    reg [1024*8:1] scope;
    begin
      if (cid == 1) begin
        u_cpu1.cpu_init();
        u_cpu1.cpu_set_name(role);
        u_cpu1.cpu_attach_pool_region(pool_base, fw_size);
        u_cpu1.cpu_set_hierarchy(hier);
        u_cpu1.cpu_attach_recorder();
        u_cpu1.cpu_attach_wdt(wdt_to);
        u_cpu1.cpu_attach_instruction_tracer(512);
        u_cpu1.cpu_attach_coverage();
        u_cpu1.cpu_attach_wave_dumper();
        $sformat(logpath, "%0s/SCPU1.log", log_dir);
        u_cpu1.cpu_open_dedicated_log(logpath);
        u_cpu1.verbose_trace = 1;
      end else if (cid == 2) begin
        u_cpu2.cpu_init();
        u_cpu2.cpu_set_name(role);
        u_cpu2.cpu_attach_pool_region(pool_base, fw_size);
        u_cpu2.cpu_set_hierarchy(hier);
        u_cpu2.cpu_attach_recorder();
        u_cpu2.cpu_attach_wdt(wdt_to);
        u_cpu2.cpu_attach_instruction_tracer(512);
        u_cpu2.cpu_attach_coverage();
        u_cpu2.cpu_attach_wave_dumper();
        $sformat(logpath, "%0s/SCPU2.log", log_dir);
        u_cpu2.cpu_open_dedicated_log(logpath);
      end else if (cid == 3) begin
        u_cpu3.cpu_init();
        u_cpu3.cpu_set_name(role);
        u_cpu3.cpu_attach_pool_region(pool_base, fw_size);
        u_cpu3.cpu_set_hierarchy(hier);
        u_cpu3.cpu_attach_recorder();
        u_cpu3.cpu_attach_wdt(wdt_to);
        u_cpu3.cpu_attach_instruction_tracer(512);
        u_cpu3.cpu_attach_coverage();
        u_cpu3.cpu_attach_wave_dumper();
        $sformat(logpath, "%0s/SCPU3.log", log_dir);
        u_cpu3.cpu_open_dedicated_log(logpath);
      end
    end
  endtask

  task print_campaign_report;
    integer tpass, tfail, tsteps, trecov;
    begin
      tpass = u_cpu1.assert_pass + u_cpu2.assert_pass + u_cpu3.assert_pass;
      tfail = u_cpu1.assert_fail + u_cpu2.assert_fail + u_cpu3.assert_fail;
      tsteps = u_cpu1.total_steps + u_cpu2.total_steps + u_cpu3.total_steps;
      trecov = u_cpu1.recovery_count + u_cpu2.recovery_count + u_cpu3.recovery_count;
      $display("==============================================================================");
      $display("VerifCPU CAMPAIGN REPORT (Verilog)");
      $display("  CPUs: 3 | Steps: %0d | Recoveries: %0d", tsteps, trecov);
      if (tpass + tfail > 0)
        $display("  Assertions: %0d PASS / %0d FAIL", tpass, tfail);
      $display("==============================================================================");
      $display("  [main        ] steps=%4d bus=%3d pc=0x%08h", u_cpu1.total_steps, u_cpu1.bus_txn_count, u_cpu1.final_pc);
      $display("  [worker      ] steps=%4d bus=%3d pc=0x%08h", u_cpu2.total_steps, u_cpu2.bus_txn_count, u_cpu2.final_pc);
      $display("  [troublemaker] steps=%4d bus=%3d pc=0x%08h recov=%0d",
               u_cpu3.total_steps, u_cpu3.bus_txn_count, u_cpu3.final_pc, u_cpu3.recovery_count);
      $display("==============================================================================");
      rpt_fd = $fopen(rpt_md, "w");
      $fwrite(rpt_fd, "# VerifCPU Campaign Report (Verilog)\n\n");
      $fwrite(rpt_fd, "- CPUs: 3\n- Steps: %0d\n- Recoveries: %0d\n", tsteps, trecov);
      $fclose(rpt_fd);
      rpt_fd = $fopen(rpt_json, "w");
      $fwrite(rpt_fd, "{\n  \"cpus\": 3,\n  \"steps\": %0d,\n  \"recoveries\": %0d\n}\n", tsteps, trecov);
      $fclose(rpt_fd);
      $display("Reports saved:\n  JSON: %0s\n  MD  : %0s", rpt_json, rpt_md);
    end
  endtask

  initial begin
    log_dir = "logs/harness_v";
    fw_path = "firmware/harness_unified.hex";
    // log_dir must exist (created by Makefile target)
    vcd_path = {log_dir, "/SCPU1.vcd"};
    rpt_json = {log_dir, "/campaign_report.json"};
    rpt_md   = {log_dir, "/campaign_report.md"};

    $display("=====================================================================================");
    $display("VerifCPU Verification Harness (Verilog)");
    $display("=====================================================================================\n");

    u_shared_bus.bus_reset();
    u_pool.pool_load_hex(fw_path);
    u_pool.pool_assign_region(1, 32'd0,   32'd68);
    u_pool.pool_assign_region(2, 32'd256, 32'd32);
    u_pool.pool_assign_region(3, 32'd512, 32'd68);

    setup_cpu(1, "main",         0, 68, 5000, 32'h10);
    setup_cpu(2, "worker",       1024, 32, 5000, 32'h20);
    setup_cpu(3, "troublemaker",   2048, 68, 6, 32'h30);

    $display("=== Setup Complete ===\n");

    $display("--- Phase 1: Initial Console Control ---");
    console_cmd(2, "stall", 0, 0, 0);
    console_cmd(1, "bus_write", 32'h5000, 32'hCAFEBABE, 4);
    console_cmd(3, "wdt_status", 0, 0, 0);
    $display("");

    $display("--- Phase 2: Running Multi-CPU Scenario ---");
    max_steps = 50;
    for (step = 0; step < max_steps; step = step + 1) begin
      if (!u_cpu1.sim_stop && (u_cpu1.state == `CPU_STATE_RUNNING || u_cpu1.state == `CPU_STATE_DUMMY))
        u_cpu1.cpu_step();
      if (!u_cpu2.sim_stop && (u_cpu2.state == `CPU_STATE_RUNNING || u_cpu2.state == `CPU_STATE_DUMMY))
        u_cpu2.cpu_step();
      if (!u_cpu3.sim_stop && (u_cpu3.state == `CPU_STATE_RUNNING || u_cpu3.state == `CPU_STATE_DUMMY))
        u_cpu3.cpu_step();

      if (step == 18) begin
        $display("\n>>> Console intervention at step 18 <<<");
        console_cmd(2, "resume", 0, 0, 0);
        console_cmd(1, "wdt_pet", 0, 0, 0);
        console_cmd(3, "bus_read", 32'h5000, 0, 4);
        $display("");
      end
      if (step == 25 && !u_cpu3.sim_stop) begin
        $display("\n>>> Explicit reset + replay on CPU3 <<<");
        u_cpu3.cpu_reset(1'b1);
        $display("");
      end
      if (u_cpu1.sim_stop && u_cpu2.sim_stop && u_cpu3.sim_stop)
        step = max_steps;
    end

    $display("\n=====================================================================================");
    $display("POST-RUN ANALYSIS");
    $display("=====================================================================================");

    $display("\n[CPU 1 - main]");
    u_cpu1.cpu_print_status();
    u_cpu1.instr_trace_print_last(4);
    u_cpu1.cov_print_summary();
    $sformat(vcd_path, "%0s/SCPU1.vcd", log_dir);
    u_cpu1.wave_export_vcd(vcd_path);

    $display("\n[CPU 2 - worker]");
    u_cpu2.cpu_print_status();
    u_cpu2.instr_trace_print_last(4);
    u_cpu2.cov_print_summary();
    $sformat(vcd_path, "%0s/SCPU2.vcd", log_dir);
    u_cpu2.wave_export_vcd(vcd_path);

    $display("\n[CPU 3 - troublemaker]");
    u_cpu3.cpu_print_status();
    u_cpu3.instr_trace_print_last(4);
    u_cpu3.cov_print_summary();
    $sformat(vcd_path, "%0s/SCPU3.vcd", log_dir);
    u_cpu3.wave_export_vcd(vcd_path);

    $display("\n=====================================================================================");
    $display("GENERATING STRUCTURED REPORT");
    $display("=====================================================================================");
    print_campaign_report();

    if (!(u_cpu1.sim_stop && u_cpu2.sim_stop)) begin
      $display("[FAIL] Harness main/worker did not reach sim_stop");
      $fatal(1, "tb_verification_harness FAILED");
    end
    if (u_cpu3.recovery_count == 0) begin
      $display("[FAIL] troublemaker expected recovery_count > 0");
      $fatal(1, "tb_verification_harness FAILED");
    end
    $display("Harness verdict: PASS (assert pass/fail=%0d/%0d, recov=%0d)",
             u_cpu1.assert_pass + u_cpu2.assert_pass + u_cpu3.assert_pass,
             u_cpu1.assert_fail + u_cpu2.assert_fail + u_cpu3.assert_fail,
             u_cpu3.recovery_count);
    $display("[SUCCESS] Harness PASS");

    u_cpu1.cpu_close_dedicated_log();
    u_cpu2.cpu_close_dedicated_log();
    u_cpu3.cpu_close_dedicated_log();

    $display("\n=====================================================================================");
    $display("Harness run complete. Logs in: %0s", log_dir);
    $display("=====================================================================================");
    $finish;
  end
endmodule