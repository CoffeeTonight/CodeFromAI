// Function tracer - mirrors tracing/tracer.py

task fn_enter;
  input [8*64:1] func_name;
  begin
    if (!trace_enabled) ;
    else if (fn_sp >= `FN_STACK_MAX)
      $display("SCPU%0d_FN > [TRACER] call stack overflow", CPU_ID);
    else begin
      fn_stack[fn_sp] = func_name;
      fn_sp = fn_sp + 1;
      trace_depth = fn_sp;
      log_fn_msg(1'b1, func_name);
    end
  end
endtask

task fn_exit;
  input [8*64:1] func_name;
  reg [8*64:1] expected;
  begin
    if (!trace_enabled) ;
    else if (fn_sp == 0) begin
      $display("SCPU%0d_FN > [TRACER WARNING] exit '%0s' with empty call stack", CPU_ID, func_name);
    end else begin
      fn_sp = fn_sp - 1;
      expected = fn_stack[fn_sp];
      if (expected != func_name)
        $display("SCPU%0d_FN > [TRACER MISMATCH] expected exit '%0s', got '%0s'",
                 CPU_ID, expected, func_name);
      trace_depth = fn_sp;
      log_fn_msg(1'b0, func_name);
    end
  end
endtask

task fn_tracer_reset;
  begin
    if (fn_sp != 0)
      $display("SCPU%0d_FN > [TRACER] clearing stack with %0d unexited frames", CPU_ID, fn_sp);
    fn_sp = 0;
    trace_depth = 0;
  end
endtask