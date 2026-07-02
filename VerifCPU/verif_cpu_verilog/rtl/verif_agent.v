// Behavior-model VerifAgent — Phase A/B/C (no cycle-accurate RV32)

`timescale 1ns/1ps
`include "verif_platform_defs.vh"
`include "campaign_manifest.vh"

module verif_agent_slave #(
  parameter [3:0]  CPU_ID = 1,
  parameter [8*8:1] CPU_NAME = "SLAVE",
  parameter [7:0]  TAP_PORT = 0
)(
  input  [1:0]      phase,
  input  [31:0]     boot_fw_offset,
  input             reset_pulse,
  input             txn_valid,
  input             txn_is_write,
  input  [31:0]     txn_addr,
  input  [31:0]     txn_data,
  input  [31:0]     icode_ptr,
  input  [2:0]      icode_kind,
  output reg [31:0] slot_count,
  output reg [31:0] verify_pass,
  output reg [31:0] verify_fail,
  output reg [31:0] txn_recorded
);

  reg [1:0]  local_phase;
  reg [31:0] local_pc;
  reg [31:0] bus_addr  [0:`MAX_SLOTS-1];
  reg [31:0] hint_addr [0:`MAX_HINTS-1];
  reg [31:0] hint_count;
  reg [31:0] init_txn_count;
  integer i;
  integer hi;
  reg     hint_seen;

  reg [31:0] expect_val;
  reg        txn_valid_q;

  function [31:0] expected_for_addr;
    input [31:0] addr;
    begin
      case (addr)
        `CAMPAIGN_MANIFEST_EXPECT_CASES
        default: expected_for_addr = 32'h0;
      endcase
    end
  endfunction

  initial begin
    local_phase    = `PHASE_INIT;
    local_pc       = `PHASE_A_OFF;
    slot_count     = 0;
    verify_pass    = 0;
    verify_fail    = 0;
    txn_recorded   = 0;
    hint_count     = 0;
    init_txn_count = 0;
    txn_valid_q    = 1'b0;
  end

  always @(posedge reset_pulse) begin
    local_pc    = boot_fw_offset;
    local_phase = phase;
    $display("SCPU%0d (%0s) > soft_reset phase=%0d pc=0x%08h",
             CPU_ID, CPU_NAME, local_phase, local_pc);
  end

  always @(txn_valid) begin
    if (txn_valid && !txn_valid_q) begin
      txn_recorded = txn_recorded + 1;
      if (local_phase == `PHASE_INIT)
        init_txn_count = init_txn_count + 1;
      if (local_phase == `PHASE_COLLECT && hint_count < `MAX_HINTS) begin
        hint_seen = 0;
        for (hi = 0; hi < hint_count; hi = hi + 1)
          if (hint_addr[hi] == txn_addr)
            hint_seen = 1;
        if (!hint_seen) begin
          hint_addr[hint_count] = txn_addr;
          hint_count = hint_count + 1;
        end
      end
    end
    txn_valid_q = txn_valid;
  end

  task run_phase_a;
    begin
      $display("SCPU%0d (%s) > Phase A: init logging (tap %0d)", CPU_ID, CPU_NAME, TAP_PORT);
      $display("SCPU%0d (%s) > Phase A done: recorded %0d txns on tap",
               CPU_ID, CPU_NAME, init_txn_count);
    end
  endtask

  task run_phase_b;
    integer h;
    begin
      $display("SCPU%0d (%s) > Phase B: collecting verification target addresses", CPU_ID, CPU_NAME);
      slot_count = 0;
      for (h = 0; h < hint_count && slot_count < `MAX_SLOTS; h = h + 1) begin
        bus_addr[slot_count] = hint_addr[h];
        $display("SCPU%0d (%s) >   slot[%0d] bus_addr=0x%08h",
                 CPU_ID, CPU_NAME, slot_count, bus_addr[slot_count]);
        slot_count = slot_count + 1;
      end
      $display("SCPU%0d (%s) > Phase B done: %0d unique addresses", CPU_ID, CPU_NAME, slot_count);
    end
  endtask

  task run_phase_c_slot;
    input [31:0] read_data;
    input [1:0]  read_resp;
    input [31:0] slot_idx;
    begin
      if (slot_idx < slot_count) begin
        expect_val = expected_for_addr(bus_addr[slot_idx]);
        $display("SCPU%0d (%s) >   vexec slot[%0d] addr=0x%08h icode_ptr=0x%08h",
                 CPU_ID, CPU_NAME, slot_idx, bus_addr[slot_idx], icode_ptr);
        $display("SCPU%0d (%s) >     read 0x%08h -> 0x%08h (expect 0x%08h)",
                 CPU_ID, CPU_NAME, bus_addr[slot_idx], read_data, expect_val);
        if (read_resp == 2'd0 && read_data == expect_val) begin
          verify_pass = verify_pass + 1;
          $display("SCPU%0d (%s) >   PASS", CPU_ID, CPU_NAME);
        end else begin
          verify_fail = verify_fail + 1;
          $display("SCPU%0d (%s) >   FAIL", CPU_ID, CPU_NAME);
        end
      end
    end
  endtask

  task run_phase_c;
    input [31:0] read_data;
    input [1:0]  read_resp;
    integer s;
    begin
      $display("SCPU%0d (%s) > Phase C: dispatch verification icode", CPU_ID, CPU_NAME);
      for (s = 0; s < slot_count; s = s + 1)
        run_phase_c_slot(read_data, read_resp, s);
      $display("SCPU%0d (%s) > Phase C done: pass=%0d fail=%0d",
               CPU_ID, CPU_NAME, verify_pass, verify_fail);
    end
  endtask

endmodule


module verif_agent_master #(
  parameter [3:0]  CPU_ID = 0,
  parameter [31:0] INIT_DONE_ADDR  = 32'h0,
  parameter [31:0] INIT_DONE_MASK  = 32'h0,
  parameter [31:0] INIT_DONE_VALUE = 32'h0,
  parameter [31:0] INIT_DONE_POLL_MAX = 32'd4096
)(
  input [1:0] phase
);

  function init_done_met;
    input [31:0] val;
    begin
      init_done_met = ((val & INIT_DONE_MASK) == INIT_DONE_VALUE);
    end
  endfunction

  task phase_release;
    input [1:0]  new_phase;
    input [31:0] fw_off;
    begin
      $display("SCPU%0d (MSTR) > phase_release -> phase=%0d", CPU_ID, new_phase);
    end
  endtask

  task inject_read_hints;
    begin
      $display("SCPU%0d (MSTR) > injecting per-slave verify targets (campaign_manifest.h)", CPU_ID);
      `CAMPAIGN_MANIFEST_MASTER_LOG
    end
  endtask

endmodule