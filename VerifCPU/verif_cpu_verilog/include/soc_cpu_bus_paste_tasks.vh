// Tasks + smoke test — included after soc_cpu_bus_paste_fabric.vh

  task paste_cli_start_vcpu;
    begin
      $display("[paste_cli] start VCPU");
      u_orch.phase_release(`PHASE_INIT, 32'h0);
    end
  endtask

  task paste_cli_release_bus;
    begin
      $display("[paste_cli] release bus");
      u_orch.phase_release(`PHASE_IDLE, 32'h0);
    end
  endtask

  integer pass, fail;
  reg [31:0] rdata, wdata;
  reg [1:0]  resp;

  task check;
    input [8*96:1] name;
    input ok;
    begin
      if (ok) begin pass = pass + 1; $display("  [PASS] %0s", name); end
      else begin fail = fail + 1; $display("  [FAIL] %0s", name); end
    end
  endtask

  initial begin
    $dumpfile("sim_build/soc_cpu_bus_paste.vcd");
    $dumpvars(0, soc_cpu_bus_paste);
    pass = 0;
    fail = 0;
    soc_rstn = 1'b0;
    repeat (4) @(posedge soc_clk);
    soc_rstn = 1'b1;
    repeat (2) @(posedge soc_clk);

    $display("========================================================================");
    $display("soc_cpu_bus_paste: copy-paste integration smoke");
    $display("========================================================================");

    wdata = 32'hA5A5_1234;
    g_slv0.u_bus.u_bridge.bus_write(SOC_PERIPH_BASE, wdata, 3'd4, resp);
    check("bridge write OK", resp == 2'd0);
    g_slv0.u_bus.u_bridge.bus_read(SOC_PERIPH_BASE, 3'd4, rdata, resp);
    check("bridge read OK", resp == 2'd0);
    check("bridge data match", rdata == wdata);
    check("agent snoop saw traffic", sl_txns > 0);

    paste_cli_start_vcpu();
    repeat (8) @(posedge soc_clk);
    paste_cli_release_bus();

    $display("Checklist: %0d passed / %0d failed", pass, fail);
    if (fail != 0) $fatal(1, "soc_cpu_bus_paste FAILED");
    $display("soc_cpu_bus_paste: PASS");
    $finish;
  end