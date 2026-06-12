// Console Debug Interface - mirrors debug/console_interface.py

module verif_cpu_console;

  // cpu_id 0 = all CPUs (set by harness before dispatch)

  task console_dispatch;
    input [3:0]    target_id;
    input [8*32:1] command;
    input [31:0]   arg0;
    input [31:0]   arg1;
    input [31:0]   arg2;
    begin
      // Implemented in harness via case on target_id calling per-cpu tasks
      $display("[Console] dispatch id=%0d cmd=%0s", target_id, command);
    end
  endtask

endmodule