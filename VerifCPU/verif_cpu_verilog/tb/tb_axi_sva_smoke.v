// AXI handshake monitor smoke (iverilog path).
// Commercial: compile sva/verif_axi_hs_sva.sv with +define+VERIF_BUS_SVA and
//             instantiate verif_axi_hs_sva on AR/AW/W (see scripts/vcs notes).
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_soc_widths.vh"
`include "verif_sim_watchdog.vh"
`include "verif_bus_axi_mon.vh"

module tb_axi_sva_smoke;

  localparam integer TB_EXPECTED_PASS = 3;

  `VERIF_SIM_WATCHDOG_NS

  localparam integer DATA_WIDTH = `VERIF_DATA_WIDTH;
  localparam integer AXI_ID_WIDTH = `VERIF_AXI_ID_WIDTH;
  localparam [31:0] BASE = 32'hA000_0000;

  reg clk = 0;
  reg aresetn = 0;
  always #5 clk = ~clk;

  wire [DATA_WIDTH-1:0] rdata;
  wire [1:0] rresp, bresp;
  wire        arready, rvalid, rlast, awready, wready, bvalid;
  wire [AXI_ID_WIDTH-1:0] rid, bid;

  verif_axi_full_master #(.AXI_PROT(4), .ID_WIDTH(AXI_ID_WIDTH), .MAX_OUTSTANDING(2)) u_mst (
    .ACLK(clk), .ARESETn(aresetn),
    .ARREADY(arready), .RVALID(rvalid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RID(rid),
    .AWREADY(awready), .WREADY(wready), .BVALID(bvalid), .BRESP(bresp), .BID(bid),
    .ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARLOCK(), .ARQOS(), .ARREGION(), .ARVALID(), .RREADY(),
    .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWLOCK(), .AWQOS(), .AWREGION(), .AWATOP(), .AWVALID(),
    .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),
    .snoop_valid(), .snoop_wr(), .snoop_addr(), .snoop_data()
  );

  verif_axi_full_slave_simple #(
    .BASE(BASE), .R_LATENCY(2), .B_LATENCY(2),
    .INIT_WORD0(32'hCAFE_0001)
  ) u_slv (
    .ACLK(clk), .ARESETn(aresetn),
    .ARID(u_mst.ARID), .ARADDR(u_mst.ARADDR), .ARLEN(u_mst.ARLEN), .ARSIZE(u_mst.ARSIZE),
    .ARBURST(u_mst.ARBURST), .ARLOCK(u_mst.ARLOCK), .ARVALID(u_mst.ARVALID), .ARREADY(arready),
    .RID(rid), .RDATA(rdata), .RRESP(rresp), .RLAST(rlast), .RVALID(rvalid), .RREADY(u_mst.RREADY),
    .AWID(u_mst.AWID), .AWADDR(u_mst.AWADDR), .AWLEN(u_mst.AWLEN), .AWSIZE(u_mst.AWSIZE),
    .AWBURST(u_mst.AWBURST), .AWLOCK(u_mst.AWLOCK), .AWVALID(u_mst.AWVALID), .AWREADY(awready),
    .WID(u_mst.WID), .WDATA(u_mst.WDATA), .WSTRB(u_mst.WSTRB), .WLAST(u_mst.WLAST),
    .WVALID(u_mst.WVALID), .WREADY(wready),
    .BID(bid), .BRESP(bresp), .BVALID(bvalid), .BREADY(u_mst.BREADY)
  );

  // Icarus path: VALID known (no X). Full VALID-until-READY is commercial SVA —
  // task-driven masters update VALID with blocking assigns after posedge, which
  // races with always @(posedge) monitors under iverilog.
  `VERIF_BUS_AXI_MON_VALID_KNOWN(clk, aresetn, u_mst.ARVALID, AR)
  `VERIF_BUS_AXI_MON_VALID_KNOWN(clk, aresetn, u_mst.AWVALID, AW)
  `VERIF_BUS_AXI_MON_VALID_KNOWN(clk, aresetn, u_mst.WVALID, W)
`ifdef VERIF_BUS_AXI_MON_STRICT
  `VERIF_BUS_AXI_MON_HS(clk, aresetn, u_mst.ARVALID, arready, AR)
  `VERIF_BUS_AXI_MON_HS(clk, aresetn, u_mst.AWVALID, awready, AW)
`endif

`ifdef VERIF_BUS_SVA
  verif_axi_hs_sva #(.TAG("AR")) u_sva_ar (
    .clk(clk), .rst_n(aresetn), .valid(u_mst.ARVALID), .ready(arready)
  );
  verif_axi_hs_sva #(.TAG("AW")) u_sva_aw (
    .clk(clk), .rst_n(aresetn), .valid(u_mst.AWVALID), .ready(awready)
  );
  verif_axi_hs_sva #(.TAG("W")) u_sva_w (
    .clk(clk), .rst_n(aresetn), .valid(u_mst.WVALID), .ready(wready)
  );
`endif

  integer pass, fail;
  reg [31:0] rd;
  reg [1:0]  resp;

  task check;
    input [255:0] name;
    input         cond;
    begin
      if (cond) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    pass = 0;
    fail = 0;
    $dumpfile("sim_build/tb_axi_sva_smoke.vcd");
    $dumpvars(0, tb_axi_sva_smoke);
    repeat (4) @(posedge clk);
    aresetn = 1'b1;
    repeat (2) @(posedge clk);

    $display("tb_axi_sva_smoke: AXI mon/SVA handshake smoke");
    u_mst.bus_write(BASE + 0, 32'hDEAD_BEEF, 3'd4, resp);
    check("write OK under mon", resp == `VERIF_BUS_RESP_OK);
    u_mst.bus_read(BASE + 0, 3'd4, rd, resp);
    check("read OK under mon", resp == `VERIF_BUS_RESP_OK && rd == 32'hDEAD_BEEF);
    u_mst.bus_write(BASE + 4, 32'h1111_2222, 3'd4, resp);
    u_mst.bus_read(BASE + 4, 3'd4, rd, resp);
    check("second xfer OK", resp == `VERIF_BUS_RESP_OK && rd == 32'h1111_2222);

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (pass != TB_EXPECTED_PASS)
      $fatal(1, "tb_axi_sva_smoke: pass=%0d expected %0d", pass, TB_EXPECTED_PASS);
    if (fail != 0)
      $fatal(1, "tb_axi_sva_smoke failed");
    $display("[SUCCESS] AXI mon/SVA smoke OK");
    $finish;
  end

endmodule
