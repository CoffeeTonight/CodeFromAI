// Integration TB — manifest bus_type + verif_vcpu_soc_cell + CONNECT_SLV* macros
// Phase A/B/C through real AMBA bridges (not simple_soc task bus).

`timescale 1ns/1ps
`include "verif_cpu_defs.vh"
`include "verif_platform_defs.vh"
`include "campaign_soc_platform.vh"
`include "campaign_manifest.vh"
`include "icode_map.vh"
`include "icode_bind.vh"
`include "verif_soc_bus_connect.vh"
`include "tb_soc_manifest_defs.vh"

module tb_soc_manifest;

  localparam FW_SIZE       = 32'h2000;
  localparam MAX_WAIT      = 32'd50000;
  localparam SOC_N         = `SOC_MANIFEST_NUM_SLAVES;
  localparam ICODE_POOL_SZ = `SOC_MANIFEST_ICODE_POOL_BYTES;

  reg soc_clk = 0;
  reg soc_rstn = 0;
  always #5 soc_clk = ~soc_clk;

  wire [1:0]  orch_phase;
  wire [31:0] orch_boot_fw;
  wire        orch_reset;
  wire [31:0] orch_reset_count;

  wire [SOC_N-1:0]        g_slv_snoop_v;
  wire [SOC_N-1:0]        g_slv_snoop_wr;
  wire [31:0] g_slv_snoop_addr [0:SOC_N-1];
  wire [31:0] g_slv_snoop_data [0:SOC_N-1];

  wire [31:0] sl_slot_count [0:SOC_N-1];
  wire [31:0] sl_pass       [0:SOC_N-1];
  wire [31:0] sl_fail       [0:SOC_N-1];
  wire [31:0] sl_txns       [0:SOC_N-1];

  wire [31:0] S01_APB_PADDR, S01_APB_PWDATA, S01_APB_PRDATA;
  wire        S01_APB_PSEL, S01_APB_PENABLE, S01_APB_PWRITE;
  wire [3:0]  S01_APB_PSTRB;
  wire        S01_APB_PREADY, S01_APB_PSLVERR;

  wire [31:0] M02_AHB_HADDR, M02_AHB_HWDATA, M02_AHB_HRDATA;
  wire [2:0]  M02_AHB_HSIZE;
  wire [1:0]  M02_AHB_HTRANS, M02_AHB_HRESP;
  wire        M02_AHB_HWRITE, M02_AHB_HREADY, M02_AHB_HREADYOUT;

  wire        S03_AXI_arvalid, S03_AXI_arready, S03_AXI_rvalid, S03_AXI_rready;
  wire        S03_AXI_awvalid, S03_AXI_awready, S03_AXI_wvalid, S03_AXI_wready;
  wire        S03_AXI_bvalid, S03_AXI_bready;
  wire [31:0] S03_AXI_araddr, S03_AXI_awaddr, S03_AXI_wdata, S03_AXI_rdata;
  wire [2:0]  S03_AXI_arsize, S03_AXI_awsize;
  wire [3:0]  S03_AXI_wstrb;
  wire [1:0]  S03_AXI_rresp, S03_AXI_bresp;
  wire [3:0]  S03_AXI_rid, S03_AXI_bid;
  wire        S03_AXI_rlast;

  verif_apb_slave_simple #(.BASE(32'h4000_0000)) u_periph_apb (
    .PCLK(soc_clk), .PRESETn(soc_rstn),
    .PADDR(S01_APB_PADDR), .PSEL(S01_APB_PSEL), .PENABLE(S01_APB_PENABLE),
    .PWRITE(S01_APB_PWRITE), .PWDATA(S01_APB_PWDATA), .PSTRB(S01_APB_PSTRB),
    .PRDATA(S01_APB_PRDATA), .PREADY(S01_APB_PREADY), .PSLVERR(S01_APB_PSLVERR)
  );

  verif_ahb_lite_slave_simple #(
    .BASE(32'h8000_0000),
    .INIT_WORD0(32'hDEADBEEF),
    .INIT_WORD1(32'hCAFEBABE)
  ) u_periph_ahb (
    .HCLK(soc_clk), .HRESETn(soc_rstn),
    .HADDR(M02_AHB_HADDR), .HSIZE(M02_AHB_HSIZE), .HTRANS(M02_AHB_HTRANS),
    .HWRITE(M02_AHB_HWRITE), .HWDATA(M02_AHB_HWDATA), .HREADY(M02_AHB_HREADY),
    .HRDATA(M02_AHB_HRDATA), .HREADYOUT(M02_AHB_HREADYOUT), .HRESP(M02_AHB_HRESP)
  );

  assign S03_AXI_rid = 4'd0;
  assign S03_AXI_bid = 4'd0;
  assign S03_AXI_rlast = 1'b1;
  verif_axi_full_slave_simple #(
    .BASE(32'hC000_0000),
    .INIT_WORD0(32'h00000080),
    .INIT_WORD1(32'hDEADDEAD)
  ) u_periph_axi (
    .ACLK(soc_clk), .ARESETn(soc_rstn),
    .ARID(4'd0), .ARADDR(S03_AXI_araddr), .ARLEN(8'd0), .ARSIZE(S03_AXI_arsize),
    .ARBURST(2'b01), .ARVALID(S03_AXI_arvalid), .ARREADY(S03_AXI_arready),
    .RID(S03_AXI_rid), .RDATA(S03_AXI_rdata), .RRESP(S03_AXI_rresp),
    .RLAST(S03_AXI_rlast), .RVALID(S03_AXI_rvalid), .RREADY(S03_AXI_rready),
    .AWID(4'd0), .AWADDR(S03_AXI_awaddr), .AWLEN(8'd0), .AWSIZE(S03_AXI_awsize),
    .AWBURST(2'b01), .AWVALID(S03_AXI_awvalid), .AWREADY(S03_AXI_awready),
    .WID(4'd0), .WDATA(S03_AXI_wdata), .WSTRB(S03_AXI_wstrb), .WLAST(1'b1),
    .WVALID(S03_AXI_wvalid), .WREADY(S03_AXI_wready),
    .BID(S03_AXI_bid), .BRESP(S03_AXI_bresp), .BVALID(S03_AXI_bvalid), .BREADY(S03_AXI_bready)
  );

  verif_orchestrator u_orch (
    .phase(orch_phase),
    .boot_fw_offset(orch_boot_fw),
    .reset_pulse(orch_reset),
    .reset_count(orch_reset_count)
  );

  verif_cpu_unified_pool #(.MEM_WORDS(32'h80000)) u_pool ();

  `CAMPAIGN_MASTER_INSTANCE

  `include "tb_soc_manifest_gen.vh"

  `ifdef CONNECT_SLV01_APB3
    `CONNECT_SLV01_APB3;
  `endif
  `ifdef CONNECT_SLV02_AHB_LITE
    `CONNECT_SLV02_AHB_LITE;
  `endif
  `ifdef CONNECT_SLV03_AXI4LITE
    `CONNECT_SLV03_AXI4LITE;
  `endif

  integer pass, fail;
  reg [31:0] rdata, orch_rst_before, total_pass, total_fail;
  reg [1:0]  rresp, rport;
  reg        icode_exec_ok, init_ok;
  integer    poll;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  task manifest_decode_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    output [1:0]  port;
    begin
      port = 2'd3;
      data = 32'hDEAD_DEAD;
      resp = 2'd2;
      if (addr >= 32'h4000_0000 && addr < 32'h4000_1000) begin
        port = 2'd0;
        g_slv0.u_bus.u_bridge.bus_read(addr, size, data, resp);
      end else if (addr >= 32'h8000_0000 && addr < 32'h8001_0000) begin
        port = 2'd1;
        g_slv1.u_bus.u_bridge.bus_read(addr, size, data, resp);
      end else if (addr >= 32'hC000_0000 && addr < 32'hC000_1000) begin
        port = 2'd2;
        g_slv2.u_bus.u_bridge.bus_read(addr, size, data, resp);
      end
    end
  endtask

  task manifest_decode_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    output [1:0]  port;
    begin
      port = 2'd3;
      resp = 2'd2;
      if (addr >= 32'h4000_0000 && addr < 32'h4000_1000) begin
        port = 2'd0;
        g_slv0.u_bus.u_bridge.bus_write(addr, data, size, resp);
      end else if (addr >= 32'h8000_0000 && addr < 32'h8001_0000) begin
        port = 2'd1;
        g_slv1.u_bus.u_bridge.bus_write(addr, data, size, resp);
      end else if (addr >= 32'hC000_0000 && addr < 32'hC000_1000) begin
        port = 2'd2;
        g_slv2.u_bus.u_bridge.bus_write(addr, data, size, resp);
      end
    end
  endtask

  task manifest_soc_run_init;
    reg [31:0] rd;
    reg [1:0] r, p;
    begin
      `SOC_MANIFEST_INIT_STEPS
    end
  endtask

  task manifest_master_wait_init_done;
    output ok;
    reg [31:0] rd;
    reg [1:0] rr;
    reg [1:0] rp;
    begin
      ok = 0;
      if (u_mstr.INIT_DONE_ADDR == 32'h0) begin
        ok = 1;
      end else begin
        for (poll = 0; poll < u_mstr.INIT_DONE_POLL_MAX; poll = poll + 1) begin
          manifest_decode_read(u_mstr.INIT_DONE_ADDR, 3'd4, rd, rr, rp);
          if (rr == 2'd0 && u_mstr.init_done_met(rd)) begin
            ok = 1;
            poll = u_mstr.INIT_DONE_POLL_MAX;
          end
        end
      end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    soc_rstn = 1'b0;
    repeat (4) @(posedge soc_clk);
    soc_rstn = 1'b1;

    $dumpfile("sim_build/tb_soc_manifest.vcd");
    $dumpvars(0, tb_soc_manifest);

    $display("========================================================================");
    $display("tb_soc_manifest: CONNECT_SLV* + verif_vcpu_soc_cell + Phase A/B/C");
    $display("========================================================================");

    `SOC_MANIFEST_LOAD_POOL
    check("Pool loaded", 1);

    `SOC_MANIFEST_SETUP_CPUS

    $display("\n[1] Phase A — SoC init + VCPU + agent snoop");
    u_orch.phase_release(`PHASE_INIT, `SOC_MANIFEST_OFF_A);
    `SOC_MANIFEST_RUN_PHASE_A

    check("SFR Phase A stopped", g_slv0.u_bus.u_cpu.sim_stop);
    check("SRAM Phase A stopped", g_slv1.u_bus.u_cpu.sim_stop);
    check("UART Phase A stopped", g_slv2.u_bus.u_cpu.sim_stop);
    check("SFR bus_txn_count > 0", g_slv0.u_bus.u_cpu.bus_txn_count > 0);
    check("SRAM bus_txn_count > 0", g_slv1.u_bus.u_cpu.bus_txn_count > 0);
    check("Agent SFR saw traffic", sl_txns[0] > 0);
    check("Agent SRAM saw traffic", sl_txns[1] > 0);
    check("Agent UART saw traffic", sl_txns[2] > 0);

    $display("\n[2] Phase B — master init_done + hints + collect");
    manifest_master_wait_init_done(init_ok);
    check("Master init_done poll", init_ok);
    `SOC_MANIFEST_RUN_PHASE_B
    check("Phase B multi-slots (2 per agent)", `SOC_MANIFEST_PHASE_B_SLOT_CHECK);

    $display("\n[3] Platform icode — RV32 exec + multi-slot verify");
    `SOC_MANIFEST_ICODE_RV32_EXEC
    `SOC_MANIFEST_ICODE_MAP_BUS_CHECKS
    `SOC_MANIFEST_ICODE_AGENT_ROUNDS
    `SOC_MANIFEST_ICODE_FINAL_CHECKS

    $display("");
    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "tb_soc_manifest FAILED");
    $display("tb_soc_manifest: PASS");
    $finish;
  end

endmodule