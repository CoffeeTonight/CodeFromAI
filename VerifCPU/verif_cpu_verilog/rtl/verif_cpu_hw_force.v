// Hierarchy-scoped HW force table — firmware vhw_force / vhw_release (custom 0x18/0x19).
// Entry (hier_id, bus_addr) -> forced read data when CPU hierarchy_id matches hier_id.

`timescale 1ns/1ps

module verif_cpu_hw_force #(
  parameter MAX_ENTRIES = 64
)(
  output reg [31:0] force_set_count,
  output reg [31:0] force_hit_count,
  output reg [31:0] active_count
);

  reg [31:0] f_hier  [0:MAX_ENTRIES-1];
  reg [31:0] f_addr  [0:MAX_ENTRIES-1];
  reg [31:0] f_val   [0:MAX_ENTRIES-1];
  reg        f_valid [0:MAX_ENTRIES-1];
  reg [7:0]  f_count;

  integer i;

  initial begin
    force_set_count = 32'd0;
    force_hit_count = 32'd0;
    active_count    = 32'd0;
    f_count         = 8'd0;
    for (i = 0; i < MAX_ENTRIES; i = i + 1) begin
      f_valid[i] = 1'b0;
      f_hier[i]  = 32'd0;
      f_addr[i]  = 32'd0;
      f_val[i]   = 32'd0;
    end
  end

  task hw_force_recount;
    reg [7:0] n;
    integer j;
    begin
      n = 8'd0;
      for (j = 0; j < MAX_ENTRIES; j = j + 1)
        if (f_valid[j])
          n = n + 8'd1;
      active_count = {24'b0, n};
    end
  endtask

  task hw_force_set;
    input [31:0] hier_id;
    input [31:0] addr;
    input [31:0] value;
    reg [7:0]    slot;
    integer      j;
    begin
      slot = 8'hFF;
      for (j = 0; j < MAX_ENTRIES; j = j + 1) begin
        if (f_valid[j] && f_hier[j] == hier_id && f_addr[j] == addr)
          slot = j[7:0];
      end
      if (slot == 8'hFF) begin
        if (f_count < MAX_ENTRIES) begin
          slot = f_count;
          f_count = f_count + 8'd1;
        end else
          slot = MAX_ENTRIES - 1;
      end
      f_hier[slot]  = hier_id;
      f_addr[slot]  = addr;
      f_val[slot]   = value;
      f_valid[slot] = 1'b1;
      force_set_count = force_set_count + 1;
      hw_force_recount();
      $display("[HWForce] set hier=0x%08h addr=0x%08h val=0x%08h (active=%0d)",
               hier_id, addr, value, active_count);
    end
  endtask

  task hw_force_clear;
    input [31:0] hier_id;
    input [31:0] addr;
    integer j;
    begin
      for (j = 0; j < MAX_ENTRIES; j = j + 1) begin
        if (f_valid[j] && f_hier[j] == hier_id && f_addr[j] == addr) begin
          f_valid[j] = 1'b0;
          $display("[HWForce] release hier=0x%08h addr=0x%08h", hier_id, addr);
        end
      end
      hw_force_recount();
    end
  endtask

  task hw_force_lookup;
    input [31:0] hier_id;
    input [31:0] addr;
    output [31:0] value;
    output        hit;
    integer j;
    begin
      hit   = 1'b0;
      value = 32'd0;
      for (j = MAX_ENTRIES - 1; j >= 0; j = j - 1) begin
        if (f_valid[j] && f_addr[j] == addr &&
            (f_hier[j] == hier_id || f_hier[j] == 32'hFFFF_FFFF)) begin
          value = f_val[j];
          hit   = 1'b1;
          j     = -1;
        end
      end
    end
  endtask

  task hw_force_record_hit;
    begin
      force_hit_count = force_hit_count + 1;
    end
  endtask

endmodule