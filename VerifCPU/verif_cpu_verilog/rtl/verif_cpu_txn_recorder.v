`include "verif_cpu_defs.vh"

module verif_cpu_txn_recorder #(
  parameter CPU_ID = 0
)(
  output reg [15:0] txn_count
);

  reg        txn_isw [0:`TXN_REC_MAX-1];
  reg [31:0] txn_addr [0:`TXN_REC_MAX-1];
  reg [31:0] txn_data [0:`TXN_REC_MAX-1];
  reg [2:0]  txn_size [0:`TXN_REC_MAX-1];
  reg [31:0] txn_cycle [0:`TXN_REC_MAX-1];
  reg [31:0] cycle;

  initial begin
    txn_count = 16'd0;
    cycle     = 32'd0;
  end

  task recorder_reset;
    integer i;
    begin
      cycle     = 32'd0;
      txn_count = 16'd0;
      for (i = 0; i < `TXN_REC_MAX; i = i + 1) begin
        txn_isw[i]   = 1'b0;
        txn_addr[i]  = 32'h0;
        txn_data[i]  = 32'h0;
        txn_size[i]  = 3'd0;
        txn_cycle[i] = 32'h0;
      end
    end
  endtask

  task recorder_record;
    input        is_write;
    input [31:0] addr;
    input [31:0] data;
    input [2:0]  size;
    reg [15:0] idx;
    begin
      if (txn_count < `TXN_REC_MAX) begin
        idx = txn_count;
        txn_isw[idx]   = is_write;
        txn_addr[idx]  = addr;
        txn_data[idx]  = data;
        txn_size[idx]  = size;
        txn_cycle[idx] = cycle;
        txn_count = txn_count + 1;
      end
      cycle = cycle + 1;
    end
  endtask

  task recorder_get_recent_count;
    output [15:0] n;
    begin
      n = txn_count;
    end
  endtask

  task recorder_last_write_to;
    input  [31:0] address;
    output        found;
    output [31:0] f_addr;
    output [31:0] f_data;
    integer i;
    begin
      found = 1'b0;
      f_addr = 32'h0;
      f_data = 32'h0;
      for (i = txn_count - 1; i >= 0; i = i - 1) begin
        if (txn_isw[i] && txn_addr[i] == address) begin
          found  = 1'b1;
          f_addr = txn_addr[i];
          f_data = txn_data[i];
          i = -1;
        end
      end
    end
  endtask

endmodule