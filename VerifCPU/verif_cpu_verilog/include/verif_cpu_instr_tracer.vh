// Instruction tracer - mirrors tracing/instruction_tracer.py

task instr_trace_snapshot;
  integer r;
  begin
    for (r = 1; r < 16; r = r + 1)
      trace_before[r] = read_reg_fn(r);
  end
endtask

task instr_trace_record;
  input [31:0] step_pc;
  input [31:0] raw;
  input [8*96:1] disasm;
  integer r;
  reg [15:0] idx;
  reg [7:0]  nchg;
  begin
    if (!instr_trace_en) ;
    else if (instr_trace_count < `INSTR_TRACE_MAX) begin
      idx = instr_trace_count;
      it_pc[idx]      = step_pc;
      it_raw[idx]     = raw;
      it_disasm[idx]  = disasm;
      it_cycle[idx]   = total_steps;
      it_bus_valid[idx] = last_bus_valid;
      it_bus_addr[idx]  = last_bus_addr;
      it_bus_data[idx]  = last_bus_data;
      it_bus_wr[idx]    = last_bus_wr;
      nchg = 0;
      for (r = 1; r < 16; r = r + 1) begin
        if (trace_before[r] != read_reg_fn(r)) begin
          it_reg_idx[idx][nchg] = r[4:0];
          it_reg_old[idx][nchg] = trace_before[r];
          it_reg_new[idx][nchg] = read_reg_fn(r);
          it_reg_chg_count[idx] = nchg + 1;
          nchg = nchg + 1;
        end
      end
      if (nchg == 0)
        it_reg_chg_count[idx] = 0;
      instr_trace_count = instr_trace_count + 1;
    end
  end
endtask

task instr_trace_print_last;
  input [7:0] n;
  reg [15:0] start;
  reg [15:0] i;
  reg [7:0]  c;
  reg [7:0]  lim;
  begin
    if (instr_trace_count == 0) begin
      $display("[SCPU%0d] No trace steps recorded.", CPU_ID);
    end else begin
      lim = (n > instr_trace_count) ? instr_trace_count[7:0] : n;
      start = instr_trace_count - lim;
      $display("\n=== SCPU%0d Rich Instruction Trace (last %0d steps) ===", CPU_ID, lim);
      for (i = start; i < instr_trace_count; i = i + 1) begin
        $write("[%04d] 0x%08h: %0s  ", it_cycle[i], it_pc[i], it_disasm[i]);
        if (it_reg_chg_count[i] == 0)
          $write("(no reg change)");
        else begin
          for (c = 0; c < it_reg_chg_count[i]; c = c + 1)
            $write("x%0d:%08h->%08h  ", it_reg_idx[i][c], it_reg_old[i][c], it_reg_new[i][c]);
        end
        if (it_bus_valid[i])
          $write("  [%0s 0x%08h = 0x%08h]", it_bus_wr[i] ? "WR" : "RD",
                 it_bus_addr[i], it_bus_data[i]);
        $write("\n");
      end
      $display("");
    end
  end
endtask