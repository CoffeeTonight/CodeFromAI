// Waveform dumper - mirrors tracing/wave_dumper.py

task wave_handle_command;
  input [31:0] cmd;
  input [31:0] arg;
  begin
    case (cmd)
      `WAVE_CMD_ON: begin
        wave_enabled = 1'b1;
        wave_chg_count = 16'd0;
        log_msg("[Wave] Dumping started");
      end
      `WAVE_CMD_OFF: begin
        wave_enabled = 1'b0;
        log_msg("[Wave] Dumping stopped");
      end
      `WAVE_CMD_DUMP_ALL: begin
        wave_dump_all = 1'b1;
        wave_scope_count = 0;
        log_msg("[Wave] Dumping ALL scopes");
      end
      `WAVE_CMD_DUMP_SCOPE: begin
        wave_dump_all = 1'b0;
        wave_scope_id[0] = arg;
        wave_scope_count = 1;
        wave_scope_name[0] = "Hier00";
        if (arg[7:0] == 8'h10) wave_scope_name[0] = "Hier10";
        $display("SCPU%0d > [Wave] Active dump scope set to: %0s", CPU_ID, wave_scope_name[0]);
      end
      default: log_msg("[WaveDumper] Unknown command");
    endcase
  end
endtask

task wave_record;
  input [8*32:1] sig;
  input [31:0]   val;
  input [8*32:1] scope;
  reg [15:0] idx;
  reg        allow;
  integer s;
  begin
    if (!wave_enabled) ;
    else if (wave_chg_count < `WAVE_CHG_MAX) begin
      allow = wave_dump_all;
      if (!allow) begin
        for (s = 0; s < wave_scope_count; s = s + 1) begin
          if (scope == wave_scope_name[s])
            allow = 1'b1;
        end
      end
      if (allow) begin
        idx = wave_chg_count;
        wave_time[idx]  = insn_pc;
        wave_sig[idx]   = sig;
        wave_val[idx]   = val;
        wave_scope[idx] = scope;
        wave_chg_count  = wave_chg_count + 1;
      end
    end
  end
endtask

task wave_export_vcd;
  input [1024*8:1] filepath;
  integer fd;
  integer i;
  integer j;
  integer nuniq;
  reg [8*32:1] uniq_sig [0:`WAVE_CHG_MAX-1];
  reg [7:0]    uniq_code [0:`WAVE_CHG_MAX-1]; // single-char id ! .. ~
  reg [31:0]   last_t;
  reg          seen;
  reg [7:0]    code;
  begin
    if (wave_chg_count == 0) begin
      log_msg("[Wave] No data to export.");
    end else begin
      // Collect unique signal names → declare $var for each (VCD requires this)
      nuniq = 0;
      for (i = 0; i < wave_chg_count; i = i + 1) begin
        seen = 1'b0;
        for (j = 0; j < nuniq; j = j + 1)
          if (uniq_sig[j] == wave_sig[i])
            seen = 1'b1;
        if (!seen && nuniq < `WAVE_CHG_MAX) begin
          uniq_sig[nuniq] = wave_sig[i];
          // printable ASCII ids starting at '!'
          uniq_code[nuniq] = 8'd33 + (nuniq % 90);
          nuniq = nuniq + 1;
        end
      end
      fd = $fopen(filepath, "w");
      $fwrite(fd, "$date\n    VerifCPU Verilog Model\n$end\n");
      $fwrite(fd, "$version\n    VerifCPU Verilog\n$end\n");
      $fwrite(fd, "$timescale 1ns $end\n\n");
      $fwrite(fd, "$scope module SCPU%0d $end\n", CPU_ID);
      for (j = 0; j < nuniq; j = j + 1)
        $fwrite(fd, "  $var wire 32 %c %0s $end\n", uniq_code[j], uniq_sig[j]);
      $fwrite(fd, "$upscope $end\n");
      $fwrite(fd, "$enddefinitions $end\n\n");
      // Sample index as time axis (insn_pc stored in wave_time is also dumped as value)
      last_t = 32'hffffffff;
      for (i = 0; i < wave_chg_count; i = i + 1) begin
        if (i != last_t) begin
          $fwrite(fd, "#%0d\n", i);
          last_t = i;
        end
        code = 8'd33;
        for (j = 0; j < nuniq; j = j + 1)
          if (uniq_sig[j] == wave_sig[i])
            code = uniq_code[j];
        // IEEE VCD: b<bits> <id>  (space before identifier)
        $fwrite(fd, "b%032b %c\n", wave_val[i], code);
      end
      $fclose(fd);
      $display("SCPU%0d > [Wave] Hierarchical VCD exported: %0s (%0d changes, %0d sigs)",
               CPU_ID, filepath, wave_chg_count, nuniq);
    end
  end
endtask