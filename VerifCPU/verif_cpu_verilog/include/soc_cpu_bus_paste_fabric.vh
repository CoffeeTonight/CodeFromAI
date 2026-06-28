// COPY into your chip_top — VCPU cell wired directly to SoC port (no CONNECT macro needed)
  generate
    begin : g_slv0
      verif_vcpu_soc_cell_axi4lite #(.CPU_ID(1)) u_bus (
        .ACLK(soc_clk),
        .ARESETn(soc_rstn),
        .ARVALID(S01_AXI_arvalid),
        .ARADDR(S01_AXI_araddr),
        .ARSIZE(S01_AXI_arsize),
        .RREADY(S01_AXI_rready),
        .AWVALID(S01_AXI_awvalid),
        .AWADDR(S01_AXI_awaddr),
        .AWSIZE(S01_AXI_awsize),
        .WVALID(S01_AXI_wvalid),
        .WDATA(S01_AXI_wdata),
        .WSTRB(S01_AXI_wstrb),
        .BREADY(S01_AXI_bready),
        .ARREADY(S01_AXI_arready),
        .RVALID(S01_AXI_rvalid),
        .RDATA(S01_AXI_rdata),
        .RRESP(S01_AXI_rresp),
        .AWREADY(S01_AXI_awready),
        .WREADY(S01_AXI_wready),
        .BVALID(S01_AXI_bvalid),
        .BRESP(S01_AXI_bresp),
        .snoop_valid(snoop_valid),
        .snoop_wr(snoop_wr),
        .snoop_addr(snoop_addr),
        .snoop_data(snoop_data)
      );
    end
  endgenerate