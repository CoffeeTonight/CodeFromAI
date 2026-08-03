// Global multi-CPU synchronization barrier for vsync (custom 0x13).
// expected[sync_id]==0 → solo marker (no wait). Non-zero mask → barrier.

`timescale 1ns/1ps

module verif_cpu_sync #(
  parameter MAX_SYNC_IDS = 64,
  parameter MAX_CPUS     = 64
)(
  output reg [31:0] barrier_release_count
);

  reg [63:0] sync_arrived  [0:MAX_SYNC_IDS-1];
  reg [63:0] sync_expected [0:MAX_SYNC_IDS-1];
  reg [31:0] sync_gen      [0:MAX_SYNC_IDS-1];

  integer i;

  initial begin
    barrier_release_count = 32'd0;
    for (i = 0; i < MAX_SYNC_IDS; i = i + 1) begin
      sync_arrived[i]  = 64'd0;
      sync_expected[i] = 64'd0;
      sync_gen[i]      = 32'd0;
    end
  end

  task sync_configure;
    input [7:0]  sync_id;
    input [63:0] participant_mask;
    reg [7:0] sid;
    begin
      sid = sync_id;
      if (sid >= MAX_SYNC_IDS)
        $fatal(1, "[Sync] configure invalid id=%0d (MAX_SYNC_IDS=%0d)", sid, MAX_SYNC_IDS);
      sync_expected[sid] = participant_mask;
      sync_arrived[sid]  = 64'd0;
      $display("[Sync] configure id=%0d expect=0x%0h", sid, participant_mask);
    end
  endtask

  function [31:0] sync_gen_snapshot;
    input [7:0] sync_id;
    begin
      if (sync_id < MAX_SYNC_IDS)
        sync_gen_snapshot = sync_gen[sync_id];
      else
        // Invalid id: do not invent gen=0 (would look like a release)
        sync_gen_snapshot = 32'hFFFF_FFFF;
    end
  endfunction

  function sync_can_resume;
    input [7:0]  cpu_id;
    input [7:0]  sync_id;
    input [31:0] wait_gen;
    reg [7:0] sid;
    begin
      sid = sync_id;
      sync_can_resume = 1'b0;
      // Invalid id must not auto-resume (arrive fatals before wait)
      if (sid >= MAX_SYNC_IDS)
        sync_can_resume = 1'b0;
      else if (sync_expected[sid] == 64'd0)
        sync_can_resume = 1'b1;
      else if (sync_gen[sid] != wait_gen)
        sync_can_resume = 1'b1;
    end
  endfunction

  // Serialize multi-CPU arrive (0-delay tasks can interleave RMW of sync_arrived).
  reg sync_lock;

  initial sync_lock = 1'b0;

  // Returns need_wait=1 if CPU must enter SYNC_WAIT until sync_can_resume is true.
  task sync_arrive;
    input  [7:0] cpu_id;
    input  [7:0] sync_id;
    output       need_wait;
    reg [7:0]    sid;
    integer      bit_i;
    reg [63:0]   arrived_masked;
    begin
      need_wait = 1'b0;
      sid = sync_id;
      // Spin until lock free (single-threaded sims: other arrive finishes first)
      while (sync_lock)
        #0;
      sync_lock = 1'b1;
      if (sid >= MAX_SYNC_IDS || cpu_id == 0 || cpu_id > MAX_CPUS) begin
        // Silent ignore weakens multi-CPU barriers — hard fail
        $fatal(1, "SCPU%0d > [Sync] VSYNC invalid (id=%0d cpu=%0d MAX_IDS=%0d MAX_CPUS=%0d)",
               cpu_id, sid, cpu_id, MAX_SYNC_IDS, MAX_CPUS);
      end else if (sync_expected[sid] == 64'd0) begin
        $display("SCPU%0d > [Sync] VSYNC solo id=%0d", cpu_id, sid);
      end else begin
        // Bit-set (not full-word RMW) so concurrent OR cannot drop another CPU's bit
        bit_i = cpu_id - 1;
        if (bit_i >= 0 && bit_i < 64)
          sync_arrived[sid][bit_i] = 1'b1;
        arrived_masked = sync_arrived[sid] & sync_expected[sid];
        $display("SCPU%0d > [Sync] VSYNC arrive id=%0d (arrived=0x%0h expect=0x%0h)",
                 cpu_id, sid, arrived_masked, sync_expected[sid]);
        if (arrived_masked == sync_expected[sid]) begin
          sync_gen[sid] = sync_gen[sid] + 1;
          sync_arrived[sid] = 64'd0;
          barrier_release_count = barrier_release_count + 1;
          $display("[Sync] barrier id=%0d RELEASE gen=%0d", sid, sync_gen[sid]);
        end else
          need_wait = 1'b1;
      end
      sync_lock = 1'b0;
    end
  endtask

endmodule