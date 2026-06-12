// VerifCPU Core - full feature parity with python_model (non-synthesizable)

`include "verif_cpu_defs.vh"


module verif_cpu_core #(
  parameter CPU_ID          = 0,
  parameter BIT_WIDTH       = 32,
  parameter FW_WORDS        = 4096,
  parameter BUS_SIZE        = 32'h100000,
  parameter WDT_DEFAULT     = 32'd10000,
  parameter USE_SHARED_BUS      = 0,
  parameter USE_SHARED_POOL     = 0,
  parameter USE_SOC_BUS         = 0,
  parameter USE_MANIFEST_SOC_BUS = 0
)(
  output reg [31:0] final_pc,
  output reg [31:0] total_steps,
  output reg        sim_stop,
  output reg [15:0] assert_pass,
  output reg [15:0] assert_fail,
  output reg [15:0] bus_txn_count,
  output reg [15:0] unique_pcs,
  output reg [31:0] recovery_count,
  output reg [7:0]  trace_depth_out,
  output reg [15:0] instr_steps_traced
);

  // --- State ---
  reg [1:0]  state;
  reg [31:0] pc;
  reg [31:0] hierarchy_id;
  reg        trace_enabled;
  reg        verbose_trace;
  reg        request_sim_stop;
  reg [8*64:1] cpu_name;

  // --- Registers ---
  reg [31:0] regs [0:31];

  // --- Force ---
  reg        forced_valid [0:31];
  reg [31:0] forced_val   [0:31];
  reg        force_active;
  reg [31:0] fmem_addr [0:`FORCED_MEM_MAX-1];
  reg [31:0] fmem_val  [0:`FORCED_MEM_MAX-1];
  reg        fmem_valid [0:`FORCED_MEM_MAX-1];
  reg [7:0]  fmem_count;
  reg [31:0] problem_addrs [0:7];
  reg [2:0]  problem_count;

  // --- Firmware (local fallback) ---
  reg [31:0] fw_words [0:127];
  reg [31:0] fw_word_count;
  reg [31:0] fw_region_base;
  reg [31:0] fw_region_size;

  // --- WDT ---
  reg [31:0] wdt_timeout;
  reg [31:0] wdt_count;
  reg        wdt_enabled;
  reg        wdt_fired;
  reg        wdt_attached;
  reg        recorder_attached;

  // --- Logging ---
  integer log_fd;

  // --- Function tracer ---
  reg [8*64:1] fn_stack [0:`FN_STACK_MAX-1];
  reg [7:0]    fn_sp;
  reg [7:0]    trace_depth;

  // --- Instruction tracer ---
  reg        instr_trace_en;
  reg [31:0] trace_before [1:15];
  reg [31:0] it_pc [0:`INSTR_TRACE_MAX-1];
  reg [31:0] it_raw [0:`INSTR_TRACE_MAX-1];
  reg [8*96:1] it_disasm [0:`INSTR_TRACE_MAX-1];
  reg [31:0] it_cycle [0:`INSTR_TRACE_MAX-1];
  reg [4:0]  it_reg_idx [0:`INSTR_TRACE_MAX-1][0:15];
  reg [31:0] it_reg_old [0:`INSTR_TRACE_MAX-1][0:15];
  reg [31:0] it_reg_new [0:`INSTR_TRACE_MAX-1][0:15];
  reg [4:0]  it_reg_chg_count [0:`INSTR_TRACE_MAX-1];
  reg        it_bus_valid [0:`INSTR_TRACE_MAX-1];
  reg [31:0] it_bus_addr [0:`INSTR_TRACE_MAX-1];
  reg [31:0] it_bus_data [0:`INSTR_TRACE_MAX-1];
  reg        it_bus_wr [0:`INSTR_TRACE_MAX-1];
  reg [15:0] instr_trace_count;

  // --- Last bus effect (for instr tracer) ---
  reg        last_bus_valid;
  reg [31:0] last_bus_addr;
  reg [31:0] last_bus_data;
  reg        last_bus_wr;
  reg [8*96:1] step_disasm;

  // --- Coverage ---
  reg        cov_en;
  reg [15:0] cov_assert_total [0:`COV_ASSERT_MAX-1];
  reg [15:0] cov_assert_passed [0:`COV_ASSERT_MAX-1];
  reg [15:0] cov_assert_failed [0:`COV_ASSERT_MAX-1];
  reg [31:0] cov_pc_list [0:`COV_PC_MAX-1];
  reg [15:0] cov_pc_hits [0:`COV_PC_MAX-1];
  reg [15:0] cov_pc_count;

  // --- Wave dumper ---
  reg        wave_enabled;
  reg        wave_dump_all;
  reg [31:0] wave_scope_id [0:3];
  reg [8*32:1] wave_scope_name [0:3];
  reg [2:0]  wave_scope_count;
  reg [31:0] wave_time [0:`WAVE_CHG_MAX-1];
  reg [8*32:1] wave_sig [0:`WAVE_CHG_MAX-1];
  reg [31:0] wave_val [0:`WAVE_CHG_MAX-1];
  reg [8*32:1] wave_scope [0:`WAVE_CHG_MAX-1];
  reg [15:0] wave_chg_count;

  // --- Submodules ---
  generate
    if (!USE_MANIFEST_SOC_BUS && !USE_SOC_BUS && !USE_SHARED_BUS) begin : g_local_bus
      verif_cpu_bus #(.BUS_SIZE(BUS_SIZE)) u_bus ();
    end
  endgenerate
  verif_cpu_txn_recorder #(.CPU_ID(CPU_ID)) u_rec (.txn_count(bus_txn_count));

  `include "verif_cpu_log.vh"
  `include "verif_cpu_xz_sanitize.vh"
  `include "verif_cpu_decode.vh"
  `include "verif_cpu_fn_tracer.vh"
  `include "verif_cpu_instr_tracer.vh"
  `include "verif_cpu_coverage.vh"
  `include "verif_cpu_wave.vh"

  // --- Register access ---
  task read_reg;
    input  [4:0]  idx;
    output [31:0] val;
    reg [31:0] raw;
    reg [8*32:1] ctx;
    begin
      if (idx == 0) raw = 32'h0;
      else if (force_active && forced_valid[idx]) raw = forced_val[idx];
      else raw = regs[idx];
      $sformat(ctx, "x%0d", idx);
      val = sanitize_xz_fn(raw, ctx);
    end
  endtask

  function [31:0] read_reg_fn;
    input [4:0] idx;
    reg [31:0] val;
    reg [8*32:1] ctx;
    begin
      if (idx == 0) val = 32'h0;
      else if (force_active && forced_valid[idx]) val = forced_val[idx];
      else val = regs[idx];
      $sformat(ctx, "x%0d", idx);
      read_reg_fn = sanitize_xz_fn(val, ctx);
    end
  endfunction

  task write_reg;
    input [4:0]  idx;
    input [31:0] val;
    begin
      if (idx == 0) ;
      else if (force_active && forced_valid[idx])
        $display("SCPU%0d > [Force] Write to forced x%0d ignored (stays 0x%08h)",
                 CPU_ID, idx, forced_val[idx]);
      else
        regs[idx] = val;
    end
  endtask

  task force_reg;
    input [4:0]  r;
    input [31:0] val;
    begin
      forced_valid[r] = 1'b1;
      forced_val[r]   = val;
      $display("SCPU%0d > [Force] x%0d forced to 0x%08h", CPU_ID, r, val);
    end
  endtask

  task release_reg;
    input [4:0] r;
    begin
      if (forced_valid[r]) begin
        forced_valid[r] = 1'b0;
        $display("SCPU%0d > [Release] x%0d released from force", CPU_ID, r);
      end
    end
  endtask

  task force_mem_addr;
    input [31:0] addr;
    input [31:0] val;
    reg [7:0] i;
    begin
      $display("SCPU%0d > [Force] MEM[0x%08h] forced to 0x%08h", CPU_ID, addr, val);
      for (i = 0; i < fmem_count; i = i + 1)
        if (fmem_valid[i] && fmem_addr[i] == addr) begin
          fmem_val[i] = val;
          i = `FORCED_MEM_MAX;
        end
      if (i != `FORCED_MEM_MAX + 1 && fmem_count < `FORCED_MEM_MAX) begin
        fmem_addr[fmem_count]  = addr;
        fmem_val[fmem_count]   = val;
        fmem_valid[fmem_count] = 1'b1;
        fmem_count = fmem_count + 1;
      end
    end
  endtask

  task release_mem_addr;
    input [31:0] addr;
    reg [7:0] i;
    begin
      for (i = 0; i < fmem_count; i = i + 1) begin
        if (fmem_valid[i] && fmem_addr[i] == addr) begin
          fmem_valid[i] = 1'b0;
          $display("SCPU%0d > [Release] MEM[0x%08h] released", CPU_ID, addr);
        end
      end
    end
  endtask

  function is_problem_addr;
    input [31:0] addr;
    reg [2:0] i;
    begin
      is_problem_addr = 1'b0;
      for (i = 0; i < problem_count; i = i + 1)
        if (problem_addrs[i] == addr)
          is_problem_addr = 1'b1;
    end
  endfunction

  task bus_read_impl;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin
      if (USE_SOC_BUS)
        tb_full_campaign.u_soc_bus.bus_read(addr, size, data, resp);
      else if (USE_SHARED_BUS)
        tb_verification_harness.u_shared_bus.bus_read(addr, size, data, resp);
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_read.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_read.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_read.vh"
`else
        data = 32'h0;
        resp = 2'd2;
`endif
      end
      else
        g_local_bus.u_bus.bus_read(addr, size, data, resp);
    end
  endtask

  task bus_write_impl;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      if (USE_SOC_BUS)
        tb_full_campaign.u_soc_bus.bus_write(addr, data, size, resp);
      else if (USE_SHARED_BUS)
        tb_verification_harness.u_shared_bus.bus_write(addr, data, size, resp);
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_write.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_write.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_write.vh"
`else
        resp = 2'd2;
`endif
      end
      else
        g_local_bus.u_bus.bus_write(addr, data, size, resp);
    end
  endtask

  task do_bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    reg [1:0] resp;
    reg [7:0] i;
    begin
      last_bus_valid = 1'b0;
      if (state == `CPU_STATE_DUMMY || is_problem_addr(addr)) begin
        data = 32'hDEADDEAD;
        last_bus_valid = 1'b1;
        last_bus_addr  = addr;
        last_bus_data  = data;
        last_bus_wr    = 1'b0;
      end else begin
        for (i = 0; i < fmem_count; i = i + 1) begin
          if (fmem_valid[i] && fmem_addr[i] == addr) begin
            data = sanitize_xz_fn(fmem_val[i], "forced_mem");
            last_bus_valid = 1'b1;
            last_bus_addr  = addr;
            last_bus_data  = data;
            last_bus_wr    = 1'b0;
            if (recorder_attached)
              u_rec.recorder_record(1'b0, addr, data, size);
            i = `FORCED_MEM_MAX;
          end
        end
        if (i != `FORCED_MEM_MAX + 1) begin
          bus_read_impl(addr, size, data, resp);
          data = sanitize_xz_fn(data, "bus_read data");
          last_bus_valid = 1'b1;
          last_bus_addr  = addr;
          last_bus_data  = data;
          last_bus_wr    = 1'b0;
          if (recorder_attached)
            u_rec.recorder_record(1'b0, addr, data, size);
          if (resp != 0)
            $display("SCPU%0d > bus read error resp=%0d @0x%08h", CPU_ID, resp, addr);
        end
      end
    end
  endtask

  task do_bus_write;
    input [31:0] addr;
    input [31:0] data;
    input [2:0]  size;
    reg [1:0] resp;
    begin
      last_bus_valid = 1'b1;
      last_bus_addr  = addr;
      last_bus_data  = data;
      last_bus_wr    = 1'b1;
      if (state == `CPU_STATE_DUMMY || is_problem_addr(addr)) begin
        if (recorder_attached)
          u_rec.recorder_record(1'b1, addr, data, size);
      end else begin
        bus_write_impl(addr, data, size, resp);
        if (recorder_attached)
          u_rec.recorder_record(1'b1, addr, data, size);
        if (resp != 0)
          $display("SCPU%0d > bus write error resp=%0d @0x%08h", CPU_ID, resp, addr);
      end
    end
  endtask

  `include "verif_cpu_custom.vh"
  `include "verif_cpu_execute.vh"

  // === Public API ===

  task cpu_init;
    integer i;
    begin
      state = `CPU_STATE_RUNNING;
      pc = 0; hierarchy_id = 0;
      trace_enabled = 1; verbose_trace = 0;
      request_sim_stop = 0; sim_stop = 0;
      total_steps = 0; recovery_count = 0;
      force_active = 1; fmem_count = 0; problem_count = 0;
      fw_region_base = 0; fw_region_size = 0; fw_word_count = 0;
      wdt_timeout = WDT_DEFAULT; wdt_count = 0;
      wdt_enabled = 1; wdt_fired = 0;
      wdt_attached = 0; recorder_attached = 0;
      log_fd = 0; fn_sp = 0; trace_depth = 0;
      instr_trace_en = 0; instr_trace_count = 0;
      cov_en = 0; wave_enabled = 0; wave_chg_count = 0;
      wave_dump_all = 1; wave_scope_count = 0;
      assert_pass = 0; assert_fail = 0; unique_pcs = 0;
      instr_steps_traced = 0; trace_depth_out = 0;
      cpu_name = "CPU";
      last_bus_valid = 0;
      for (i = 0; i < 32; i = i + 1) begin
        regs[i] = 0; forced_valid[i] = 0; forced_val[i] = 0;
      end
      if (!USE_SHARED_BUS && !USE_MANIFEST_SOC_BUS && !USE_SOC_BUS)
        g_local_bus.u_bus.bus_reset();
      u_rec.recorder_reset();
      cov_reset();
      fn_tracer_reset();
    end
  endtask

  task cpu_set_name;
    input [8*64:1] name;
    begin cpu_name = name; end
  endtask

  task cpu_load_firmware;
    input [1024*8:1] hexfile;
    input [31:0]     region_base;
    input [31:0]     region_size;
    begin
      fw_region_base = region_base;
      fw_region_size = region_size;
      fw_word_count  = region_size >> 2;
      $readmemh(hexfile, fw_words);
      $display("[UnifiedPool] CPU%0d firmware loaded from %0s (%0d words)",
               CPU_ID, hexfile, fw_word_count);
    end
  endtask

  task cpu_attach_pool_region;
    input [31:0] region_base;
    input [31:0] region_size;
    begin
      fw_region_base = region_base;
      fw_region_size = region_size;
      fw_word_count  = region_size >> 2;
      $display("SCPU%0d > Firmware attached: offset=0x%08h, size=%0d", CPU_ID, region_base, region_size);
    end
  endtask

  task cpu_set_hierarchy;
    input [31:0] hid;
    begin
      hierarchy_id = hid;
      $display("SCPU%0d > Hierarchy set to 0x%08h", CPU_ID, hid);
    end
  endtask

  task enter_dummy_mode;
    begin
      state = `CPU_STATE_DUMMY;
      $display("SCPU%0d > Entered DUMMY_MODE", CPU_ID);
      log_msg("Entered dummy data mode");
    end
  endtask

  task exit_dummy_mode;
    begin
      if (state == `CPU_STATE_DUMMY) begin
        state = `CPU_STATE_RUNNING;
        $display("SCPU%0d > Exited DUMMY_MODE", CPU_ID);
      end
    end
  endtask

  task cpu_stall;
    begin
      if (state == `CPU_STATE_RUNNING) begin
        state = `CPU_STATE_STALLED;
        log_msg("Stalled");
      end
    end
  endtask

  task cpu_resume;
    begin
      if (state == `CPU_STATE_STALLED) begin
        state = `CPU_STATE_RUNNING;
        log_msg("Resumed");
      end
    end
  endtask

  task cpu_attach_recorder;
    begin
      recorder_attached = 1'b1;
      $display("SCPU%0d > Transaction recorder attached", CPU_ID);
    end
  endtask

  task cpu_attach_wdt;
    input [31:0] timeout;
    begin
      wdt_attached = 1'b1;
      wdt_timeout  = (timeout == 0) ? WDT_DEFAULT : timeout;
      wdt_enabled  = 1'b1;
      $display("SCPU%0d > WDT attached (timeout=%0d)", CPU_ID, wdt_timeout);
    end
  endtask

  task cpu_attach_instruction_tracer;
    input [15:0] max_steps;
    begin
      instr_trace_en = 1'b1;
      instr_trace_count = 0;
      $display("SCPU%0d > Rich InstructionTracer attached (max_steps=%0d)", CPU_ID, max_steps);
    end
  endtask

  task cpu_attach_coverage;
    begin
      cov_en = 1'b1;
      log_msg("[Coverage] Collector attached");
    end
  endtask

  task cpu_attach_wave_dumper;
    begin
      wave_enabled = 1'b0;
      log_msg("[Wave] WaveDumper attached");
    end
  endtask

  task cpu_open_dedicated_log;
    input [1024*8:1] path;
    begin
      log_fd = $fopen(path, "a");
      $display("SCPU%0d > Dedicated log opened: %0s", CPU_ID, path);
      if (log_fd != 0)
        $fwrite(log_fd, "SCPU%0d > Dedicated log opened: %0s\n", CPU_ID, path);
    end
  endtask

  task cpu_close_dedicated_log;
    begin
      if (log_fd != 0) $fclose(log_fd);
      log_fd = 0;
    end
  endtask

  task cpu_reset;
    input replay_txns;
    integer i;
    begin
      state = `CPU_STATE_RESET;
      pc = 0; request_sim_stop = 0;
      for (i = 0; i < 32; i = i + 1) regs[i] = 0;
      fn_tracer_reset();
      log_msg("Reset");
      if (replay_txns && bus_txn_count > 0)
        cpu_replay_transactions();
      state = `CPU_STATE_RUNNING;
    end
  endtask

  task cpu_replay_transactions;
    reg [15:0] n, slot;
    reg [1:0]  resp;
    reg [31:0] rdata;
    begin
      n = bus_txn_count;
      $display("SCPU%0d > Replaying %0d recorded transactions...", CPU_ID, n);
      for (slot = 0; slot < n; slot = slot + 1) begin
        if (u_rec.txn_isw[slot]) begin
          bus_write_impl(u_rec.txn_addr[slot], u_rec.txn_data[slot], u_rec.txn_size[slot], resp);
          $display("SCPU%0d > [Replay] Write 0x%08h <= 0x%08h", CPU_ID,
                   u_rec.txn_addr[slot], u_rec.txn_data[slot]);
        end else begin
          bus_read_impl(u_rec.txn_addr[slot], u_rec.txn_size[slot], rdata, resp);
          $display("SCPU%0d > [Replay] Read  0x%08h => 0x%08h", CPU_ID,
                   u_rec.txn_addr[slot], rdata);
        end
      end
      log_msg("Transaction replay complete. Continuing own firmware...");
    end
  endtask

  task wdt_default_recovery;
    reg [15:0] last_idx;
    begin
      $display("SCPU%0d > WDT recovery triggered - reset + full transaction replay + continue own code", CPU_ID);
      recovery_count = recovery_count + 1;
      if (bus_txn_count > 0) begin
        last_idx = bus_txn_count - 1;
        if (problem_count < 7) begin
          problem_addrs[problem_count] = u_rec.txn_addr[last_idx];
          problem_count = problem_count + 1;
        end
      end
      cpu_reset(1'b1);
      enter_dummy_mode();
      if (problem_count > 0)
        $display("SCPU%0d > Entered dummy mode for suspect addrs", CPU_ID);
      wdt_count = 0; wdt_fired = 0;
    end
  endtask

  task wdt_tick;
    begin
      if (!wdt_attached || !wdt_enabled || wdt_fired) ;
      else begin
        wdt_count = wdt_count + 1;
        if (wdt_count >= wdt_timeout) begin
          wdt_fired = 1'b1;
          $display("SCPU%0d > *** WDT TIMEOUT *** (%0d cycles, limit=%0d)",
                   CPU_ID, wdt_count, wdt_timeout);
          wdt_default_recovery();
        end
      end
    end
  endtask

  task cpu_wdt_pet;
    begin
      wdt_count = 0; wdt_fired = 0;
      log_msg("[Console] WDT petted via console");
    end
  endtask

  task cpu_wdt_status;
    begin
      $display("SCPU%0d > [Console] WDT(cpu=%0d, enabled=%0d, count=%0d/%0d, fired=%0d)",
               CPU_ID, CPU_ID, wdt_enabled, wdt_count, wdt_timeout, wdt_fired);
    end
  endtask

  task cpu_console_bus_write;
    input [31:0] addr;
    input [31:0] data;
    input [2:0]  size;
    reg [1:0] resp;
    begin
      bus_write_impl(addr, data, size, resp);
      if (recorder_attached)
        u_rec.recorder_record(1'b1, addr, data, size);
      $display("SCPU%0d > [Console Bus Master] WRITE 0x%08h <= 0x%08h (size=%0d) -> %0s",
               CPU_ID, addr, data, size, (resp == 0) ? "OK" : "ERR");
    end
  endtask

  task cpu_console_bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    reg [1:0] resp;
    begin
      bus_read_impl(addr, size, data, resp);
      if (recorder_attached)
        u_rec.recorder_record(1'b0, addr, data, size);
      $display("SCPU%0d > [Console Bus Master] READ  0x%08h => 0x%08h (size=%0d) -> %0s",
               CPU_ID, addr, data, size, (resp == 0) ? "OK" : "ERR");
    end
  endtask

  task cpu_fetch;
    output [31:0] instr;
    output        err;
    reg [31:0] word_idx;
    begin
      err = 1'b0;
      instr = 32'h00000013;
      if (fw_word_count == 0 && !USE_SHARED_POOL) begin
        $display("SCPU%0d > 0x%08h: nop (no firmware)", CPU_ID, pc);
      end else if (USE_SOC_BUS) begin
        tb_full_campaign.u_pool.pool_read_word(CPU_ID[3:0], pc, instr, err);
      end else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
        tb_soc_manifest_scale.u_pool.pool_read_word(CPU_ID[3:0], pc, instr, err);
`elsif VERIF_MANIFEST_SOC_TB
        tb_soc_manifest.u_pool.pool_read_word(CPU_ID[3:0], pc, instr, err);
`elsif VERIF_CHIP_SOC_TB
        chip_top_example.u_pool.pool_read_word(CPU_ID[3:0], pc, instr, err);
`else
        err = 1'b1;
`endif
      end else if (USE_SHARED_POOL) begin
        tb_verification_harness.u_pool.pool_read_word(CPU_ID[3:0], pc, instr, err);
        if (err) state = `CPU_STATE_STALLED;
      end else if (pc + 4 > fw_region_size) begin
        $display("SCPU%0d > Firmware read error at pc=0x%08h", CPU_ID, pc);
        state = `CPU_STATE_STALLED; err = 1'b1;
      end else begin
        word_idx = (fw_region_base + pc) >> 2;
        instr = fw_words[word_idx];
      end
    end
  endtask

  task cpu_log_nop;
    begin
      $display("SCPU%0d > 0x%08h: addi x0,x0,0", CPU_ID, pc);
      step_disasm = "addi x0,x0,0";
    end
  endtask

  task cpu_wave_tick;
    reg [8*32:1] scope;
    reg [31:0] r;
    begin
      if (!wave_enabled) ;
      else begin
        $sformat(scope, "Hier%02h", hierarchy_id[7:0]);
        wave_record("pc", pc, scope);
        r = 1; wave_record("x1", read_reg_fn(1), scope);
        r = 2; wave_record("x2", read_reg_fn(2), scope);
        r = 3; wave_record("x3", read_reg_fn(3), scope);
      end
    end
  endtask

  task cpu_verbose_regs;
    reg [31:0] r1,r2,r3,r4,r5;
    begin
      r1=read_reg_fn(1); r2=read_reg_fn(2); r3=read_reg_fn(3);
      r4=read_reg_fn(4); r5=read_reg_fn(5);
      $display("SCPU%0d >   regs: x1=%08h x2=%08h x3=%08h x4=%08h x5=%08h",
               CPU_ID, r1,r2,r3,r4,r5);
    end
  endtask

  task cpu_step;
    reg [31:0] raw;
    reg        pc_updated, fetch_err;
    reg [6:0]  opcode;
    reg [4:0]  rd, rs1, rs2;
    reg [2:0]  funct3;
    reg [6:0]  funct7;
    reg [31:0] imm;
    reg        is_custom;
    reg [8*96:1] cdisasm;
    begin
      if (state != `CPU_STATE_RUNNING && state != `CPU_STATE_DUMMY) ;
      else begin
        total_steps = total_steps + 1;
        if (instr_trace_en) instr_trace_snapshot();
        cpu_fetch(raw, fetch_err);
        if (fetch_err) ;
        else begin
          decode_instruction(raw, opcode, rd, rs1, rs2, funct3, funct7, imm, is_custom);
          if (fw_word_count == 0 && !USE_SHARED_POOL) cpu_log_nop();

          if (is_custom) begin
            if (funct7 == `VSEL_STOP) begin
              step_disasm = "vstop (custom)"; log_inst(pc, step_disasm);
            end else if (funct7 == `VSEL_DUMMY_ON) begin
              step_disasm = "vdummy_on (custom)"; log_inst(pc, step_disasm);
            end else begin
              $sformat(step_disasm, "custom0 sel=0x%02h", funct7);
              log_inst(pc, step_disasm);
            end
            exec_custom(funct7, rd, rs1, rs2, imm);
            pc = pc + 4;
          end else begin
            execute_instruction(raw, pc_updated);
            if (!pc_updated) pc = pc + 4;
          end

          if (cov_en) cov_record_pc(pc);
          cpu_wave_tick();
          if (instr_trace_en) instr_trace_record(pc, raw, step_disasm);
          wdt_tick();
          if (verbose_trace) cpu_verbose_regs();
        end
        final_pc = pc;
        sim_stop = request_sim_stop;
        trace_depth_out = trace_depth;
        instr_steps_traced = instr_trace_count;
        unique_pcs = cov_pc_count;
      end
    end
  endtask

  task cpu_dump_regs;
    reg [31:0] r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11;
    begin
      r0=read_reg_fn(0); r1=read_reg_fn(1); r2=read_reg_fn(2);
      r3=read_reg_fn(3); r4=read_reg_fn(4); r5=read_reg_fn(5);
      r6=read_reg_fn(6); r7=read_reg_fn(7); r8=read_reg_fn(8);
      r9=read_reg_fn(9); r10=read_reg_fn(10); r11=read_reg_fn(11);
      $display("SCPU%0d > REG  x0=%08h  x1=%08h  x2=%08h  x3=%08h  x4=%08h  x5=%08h",
               CPU_ID, r0,r1,r2,r3,r4,r5);
      $display("SCPU%0d >      x6=%08h  x7=%08h  x8=%08h  x9=%08h x10=%08h x11=%08h",
               CPU_ID, r6,r7,r8,r9,r10,r11);
    end
  endtask

  task cpu_print_status;
    reg [8*16:1] st;
    begin
      case (state)
        `CPU_STATE_RUNNING: st = "RUNNING";
        `CPU_STATE_STALLED: st = "STALLED";
        `CPU_STATE_RESET:   st = "RESET";
        `CPU_STATE_DUMMY:   st = "DUMMY_MODE";
        default: st = "UNKNOWN";
      endcase
      $display("VerifCPU(id=%0d, width=%0d, state=%0s, pc=0x%08h)",
               CPU_ID, BIT_WIDTH, st, pc);
    end
  endtask

  task cpu_get_metrics_print;
    begin
      $display("  cpu_id=%0d name=%0s steps=%0d recov=%0d bus_txn=%0d pcs=%0d instr_trace=%0d",
               CPU_ID, cpu_name, total_steps, recovery_count, bus_txn_count,
               unique_pcs, instr_trace_count);
    end
  endtask

endmodule