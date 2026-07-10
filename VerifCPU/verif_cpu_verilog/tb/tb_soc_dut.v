// tb_dut: SimpleSoC + orchestrator + generate VCPUs (iverilog behavior model)
// Mirrors python_model/demo_soc_tb.py

`timescale 1ns/1ps
`include "verif_platform_defs.vh"
`include "campaign_soc_platform.vh"
`include "verif_sim_watchdog.vh"

module tb_soc_dut;

  localparam NUM_SLAVES = 3;
  localparam integer TB_EXPECTED_PASS = 3;

  `VERIF_SIM_WATCHDOG_NS

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;
  wire [31:0] orch_reset_count;

  wire [31:0] sl_slot_count [0:NUM_SLAVES-1];
  wire [31:0] sl_pass       [0:NUM_SLAVES-1];
  wire [31:0] sl_fail       [0:NUM_SLAVES-1];
  wire [31:0] sl_txns       [0:NUM_SLAVES-1];

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count(orch_reset_count)
  );

  simple_soc u_soc ();

  genvar i;
  generate
    for (i = 0; i < NUM_SLAVES; i = i + 1) begin : g_slave
      localparam [3:0]  CID = i + 1;
      localparam [1:0]  TAP = i[1:0];
      localparam [31:0] ICODE_PTR = 32'h1000 * (i + 1);
      localparam [2:0]  ICODE_KIND = i[2:0];

      verif_agent_slave #(
        .CPU_ID(CID),
        .CPU_NAME((i == 0) ? "SFR   " : (i == 1) ? "SRAM  " : "UART  "),
        .TAP_PORT(TAP)
      ) u_ag (
        .phase(orch_phase),
        .boot_fw_offset(orch_boot_fw),
        .reset_pulse(orch_reset),
        .txn_valid(u_soc.stxn_valid[TAP]),
        .txn_is_write(u_soc.stxn_wr[TAP]),
        .txn_addr(u_soc.stxn_addr[TAP]),
        .txn_data(u_soc.stxn_data[TAP]),
        .icode_ptr(ICODE_PTR),
        .icode_kind(ICODE_KIND),
        .slot_count(sl_slot_count[i]),
        .verify_pass(sl_pass[i]),
        .verify_fail(sl_fail[i]),
        .txn_recorded(sl_txns[i])
      );
    end
  endgenerate

  `CAMPAIGN_MASTER_INSTANCE

  reg [31:0] total_pass;
  reg [31:0] total_fail;
  reg [31:0] rdata;
  reg [1:0]  rresp;
  reg [1:0]  rport;
  integer gi;

  initial begin
    $dumpfile("sim_build/tb_soc_dut.vcd");
    $dumpvars(0, tb_soc_dut);
    total_pass = 0;
    total_fail = 0;

    $display("========================================================================");
    $display("tb_soc_dut: SimpleSoC + VerifCPU agents (iverilog behavior model)");
    $display("========================================================================");

    $display("");
    $display("[1] Phase A - SoC init + slave snoop");
    u_orch.phase_release(`PHASE_INIT, 32'h0);
    u_soc.run_init();
    g_slave[0].u_ag.run_phase_a();
    g_slave[1].u_ag.run_phase_a();
    g_slave[2].u_ag.run_phase_a();

    $display("");
    $display("[2] Phase B - master waits init_done then injects targets");
    begin
      reg [31:0] rd;
      reg [1:0] rr, rp;
      integer poll;
      reg init_ok;
      init_ok = 0;
      for (poll = 0; poll < u_mstr.INIT_DONE_POLL_MAX; poll = poll + 1) begin
        u_soc.decode_read(u_mstr.INIT_DONE_ADDR, 3'd4, rd, rr, rp);
        if (rr == 2'd0 && u_mstr.init_done_met(rd)) begin
          init_ok = 1;
          poll = u_mstr.INIT_DONE_POLL_MAX;
        end
      end
      if (!init_ok) $fatal(1, "Master init_done poll failed");
    end
    u_mstr.phase_release(`PHASE_COLLECT, 32'h0);
    u_orch.phase_release(`PHASE_COLLECT, 32'h0);
    u_mstr.inject_read_hints();
    u_soc.decode_read(32'h4000_0000, 3'd4, rdata, rresp, rport);
    u_soc.decode_read(32'h8000_0000, 3'd4, rdata, rresp, rport);
    u_soc.decode_read(32'hC000_0000, 3'd4, rdata, rresp, rport);
    g_slave[0].u_ag.run_phase_b();
    g_slave[1].u_ag.run_phase_b();
    g_slave[2].u_ag.run_phase_b();

    $display("");
    $display("[3] Host bind - icode_ptr -> program store");
    $display("    CPU1 (SFR)  slot[0] icode_ptr=0x1000");
    $display("    CPU2 (SRAM) slot[0] icode_ptr=0x2000");
    $display("    CPU3 (UART) slot[0] icode_ptr=0x3000");

    $display("");
    $display("[4] Phase C - slave icode execution");
    u_mstr.phase_release(`PHASE_VERIFY, 32'h0);
    u_orch.phase_release(`PHASE_VERIFY, 32'h0);
    begin : phase_c_sfr
      integer s;
      for (s = 0; s < g_slave[0].u_ag.slot_count; s = s + 1) begin
        u_soc.decode_read(g_slave[0].u_ag.bus_addr[s], 3'd4, rdata, rresp, rport);
        g_slave[0].u_ag.run_phase_c_slot(rdata, rresp, s);
      end
    end
    begin : phase_c_sram
      integer s;
      for (s = 0; s < g_slave[1].u_ag.slot_count; s = s + 1) begin
        u_soc.decode_read(g_slave[1].u_ag.bus_addr[s], 3'd4, rdata, rresp, rport);
        g_slave[1].u_ag.run_phase_c_slot(rdata, rresp, s);
      end
    end
    begin : phase_c_uart
      integer s;
      for (s = 0; s < g_slave[2].u_ag.slot_count; s = s + 1) begin
        u_soc.decode_read(g_slave[2].u_ag.bus_addr[s], 3'd4, rdata, rresp, rport);
        g_slave[2].u_ag.run_phase_c_slot(rdata, rresp, s);
      end
    end

    $display("");
    $display("========================================================================");
    $display("Campaign Report");
    $display("========================================================================");
    for (gi = 0; gi < NUM_SLAVES; gi = gi + 1) begin
      $display("  slave%0d txns=%0d slots=%0d PASS=%0d FAIL=%0d",
               gi + 1, sl_txns[gi], sl_slot_count[gi], sl_pass[gi], sl_fail[gi]);
      total_pass = total_pass + sl_pass[gi];
      total_fail = total_fail + sl_fail[gi];
    end
    $display("");
    $display("  TOTAL: PASS=%0d FAIL=%0d", total_pass, total_fail);
    $display("========================================================================");

    if (total_fail != 0 || total_pass != TB_EXPECTED_PASS) begin
      $display("[FAIL] SoC verification campaign failed (pass=%0d expected %0d).",
               total_pass, TB_EXPECTED_PASS);
      $fatal(1);
    end
    $display("[SUCCESS] SoC verification campaign completed.");
    $finish;
  end

endmodule