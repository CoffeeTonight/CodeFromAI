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
        wave_time[idx]  = pc;
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
  reg [15:0] i;
  reg [31:0] last_t;
  begin
    if (wave_chg_count == 0) begin
      log_msg("[Wave] No data to export.");
    end else begin
      fd = $fopen(filepath, "w");
      $fwrite(fd, "$date\n    VerifCPU Verilog Model\n$end\n");
      $fwrite(fd, "$version\n    VerifCPU Verilog\n$end\n");
      $fwrite(fd, "$timescale 1ns $end\n\n");
      $fwrite(fd, "$scope module SCPU%0d $end\n", CPU_ID);
      $fwrite(fd, "  $var reg 32 pc pc $end\n");
      $fwrite(fd, "$upscope $end\n$enddefinitions $end\n\n");
      last_t = 32'hffffffff;
      for (i = 0; i < wave_chg_count; i = i + 1) begin
        if (wave_time[i] != last_t) begin
          $fwrite(fd, "#%0d\n", wave_time[i]);
          last_t = wave_time[i];
        end
        $fwrite(fd, "b%032b %0s\n", wave_val[i], wave_sig[i]);
      end
      $fclose(fd);
      $display("SCPU%0d > [Wave] Hierarchical VCD exported: %0s (%0d changes)",
               CPU_ID, filepath, wave_chg_count);
    end
  end
endtask