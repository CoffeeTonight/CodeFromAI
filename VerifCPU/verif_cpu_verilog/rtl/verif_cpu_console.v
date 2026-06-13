// Console Debug Interface — mirrors python_model/verif_cpu/debug/console_interface.py
// Implementation lives in verif_cpu_core (cpu_console_dispatch / cpu_console_custom).
// TB modules expose console_cmd() for EDA UCLI: call tb_full_campaign.console_cmd(...)

module verif_cpu_console;

  task console_dispatch;
    input [3:0]    target_id;
    input [8*32:1] command;
    input [31:0]   arg0;
    input [31:0]   arg1;
    input [31:0]   arg2;
    begin
      $display("[Console] use TB console_cmd — e.g. call tb_full_campaign.console_cmd(%0d, %0s, ...)",
               target_id, command);
    end
  endtask

endmodule