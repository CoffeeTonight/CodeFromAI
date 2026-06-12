// SCPUx logging with optional dedicated log file

task log_out;
  input [8*256:1] msg;
  begin
    if (trace_enabled) begin
      $display("SCPU%0d > %0s", CPU_ID, msg);
      if (log_fd != 0) begin
        $fwrite(log_fd, "SCPU%0d > %0s\n", CPU_ID, msg);
      end
    end
  end
endtask

task log_msg;
  input [8*256:1] msg;
  begin
    log_out(msg);
  end
endtask

task log_fn_msg;
  input        is_enter;
  input [8*96:1] name;
  reg [8*128:1] line;
  begin
    if (!trace_enabled) ;
    else begin
      if (is_enter) begin
        $display("SCPU%0d_FN > %0s%0s enter", CPU_ID, fn_indent(), name);
        if (log_fd != 0)
          $fwrite(log_fd, "SCPU%0d_FN > %0s%0s enter\n", CPU_ID, fn_indent(), name);
      end else begin
        $display("SCPU%0d_FN > %0s%0s exit", CPU_ID, fn_indent(), name);
        if (log_fd != 0)
          $fwrite(log_fd, "SCPU%0d_FN > %0s%0s exit\n", CPU_ID, fn_indent(), name);
      end
    end
  end
endtask

task log_inst;
  input [31:0] pc_val;
  input [8*96:1] disasm;
  begin
    if (trace_enabled) begin
      $display("SCPU%0d > 0x%08h: %0s", CPU_ID, pc_val, disasm);
      if (log_fd != 0)
        $fwrite(log_fd, "SCPU%0d > 0x%08h: %0s\n", CPU_ID, pc_val, disasm);
    end
  end
endtask

function [8*32:1] fn_indent;
  integer i;
  reg [8*32:1] s;
  begin
    s = "";
    for (i = 0; i < trace_depth; i = i + 1)
      s = {s, "  "};
    fn_indent = s;
  end
endfunction