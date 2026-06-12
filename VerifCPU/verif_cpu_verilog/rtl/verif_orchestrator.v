// TB-level phase orchestrator

`timescale 1ns/1ps
`include "verif_platform_defs.vh"

module verif_orchestrator (
  output reg [1:0]  phase,
  output reg [31:0] boot_fw_offset,
  output reg        reset_pulse,
  output reg [31:0] reset_count
);

  initial begin
    phase          = `PHASE_INIT;
    boot_fw_offset = `PHASE_A_OFF;
    reset_pulse    = 1'b0;
    reset_count    = 32'h0;
  end

  task phase_release;
    input [1:0]  new_phase;
    input [31:0] fw_off;
    begin
      phase = new_phase;
      if (fw_off == 32'h0) begin
        case (new_phase)
          `PHASE_INIT:    boot_fw_offset = `PHASE_A_OFF;
          `PHASE_COLLECT: boot_fw_offset = `PHASE_B_OFF;
          `PHASE_VERIFY:  boot_fw_offset = `PHASE_C_OFF;
          default:        boot_fw_offset = `PHASE_C_OFF;
        endcase
      end else
        boot_fw_offset = fw_off;
      reset_pulse = 1'b1;
      reset_count = reset_count + 1;
      #1 reset_pulse = 1'b0;
      $display("[Orch] phase_release phase=%0d boot_fw=0x%08h", new_phase, boot_fw_offset);
    end
  endtask

  // Soft-reset pulse between consecutive icode slot executions (phase unchanged)
  task icode_inter_reset;
    begin
      reset_pulse = 1'b1;
      reset_count = reset_count + 1;
      #1 reset_pulse = 1'b0;
      $display("[Orch] icode_inter_reset count=%0d", reset_count);
    end
  endtask

endmodule