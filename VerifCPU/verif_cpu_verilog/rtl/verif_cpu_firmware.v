// Unified firmware pool (file-backed, mirrors unified_pool.py)

module verif_cpu_firmware #(
  parameter MEM_BYTES = 32'h10000
)(
  input wire [31:0] cpu_id,
  input wire [31:0] region_base,
  input wire [31:0] region_size,
  input wire [31:0] offset,
  input wire [2:0]  read_size,
  output reg [31:0] data,
  output reg        error
);

  reg [7:0] pool [0:MEM_BYTES-1];
  integer i;

  task fw_load_hex;
    input [1024*8:1] filename;
    begin
      $readmemh(filename, pool);
      $display("[UnifiedPool] Loaded firmware from %0s", filename);
    end
  endtask

  task fw_clear;
    begin
      for (i = 0; i < MEM_BYTES; i = i + 1)
        pool[i] = 8'h0;
    end
  endtask

  task fw_read;
    input  [31:0] rd_offset;
    input  [2:0]  rd_size;
    output [31:0] rd_data;
    output        rd_error;
    integer j;
    reg [31:0] abs_addr;
    reg [31:0] tmp;
    begin
      rd_error = 1'b0;
      rd_data  = 32'h0;
      if (rd_offset + rd_size > region_size) begin
        rd_error = 1'b1;
        $display("[UnifiedPool] CPU%0d read beyond region offset=0x%08h", cpu_id, rd_offset);
      end else begin
        abs_addr = region_base + rd_offset;
        tmp = 32'h0;
        for (j = 0; j < rd_size; j = j + 1)
          tmp[j*8 +: 8] = pool[abs_addr + j];
        rd_data = tmp;
      end
    end
  endtask

endmodule