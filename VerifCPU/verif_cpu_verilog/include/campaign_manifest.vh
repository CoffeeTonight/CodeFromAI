// Auto-generated from firmware/campaign/include/campaign_manifest.h
`ifndef CAMPAIGN_MANIFEST_VH
`define CAMPAIGN_MANIFEST_VH

`define MANIFEST_SLAVE_COUNT 60

// Master Phase B: inject bus_read per slave target (TB calls decode_read)
`define CAMPAIGN_MANIFEST_MASTER_LOG \
  $display("SCPU0 (MSTR) > hint slave=SFR tap=0 addr=0x%08h expect=0x%08h icode=%s", 32'h40000000, 32'h00000001, "check_sfr_ctrl"); \
  $display("SCPU0 (MSTR) > hint slave=SFR tap=0 addr=0x%08h expect=0x%08h icode=%s", 32'h40000004, 32'h000000FF, "check_sfr_mask"); \
  $display("SCPU0 (MSTR) > hint slave=SRAM tap=1 addr=0x%08h expect=0x%08h icode=%s", 32'h80000000, 32'hDEADBEEF, "check_sram_marker"); \
  $display("SCPU0 (MSTR) > hint slave=SRAM tap=1 addr=0x%08h expect=0x%08h icode=%s", 32'h80000004, 32'hCAFEBABE, "check_sram_aux"); \
  $display("SCPU0 (MSTR) > hint slave=UART tap=2 addr=0x%08h expect=0x%08h icode=%s", 32'hC0000000, 32'h00000080, "check_uart_baud"); \
  $display("SCPU0 (MSTR) > hint slave=UART tap=2 addr=0x%08h expect=0x%08h icode=%s", 32'hC0000010, 32'hDEADDEAD, "check_uart_irq"); \

`define CAMPAIGN_MANIFEST_BUS_READS \
  u_soc.decode_read(32'h40000000, 3'd4, rdata, rresp, rport); \
  u_soc.decode_read(32'h40000004, 3'd4, rdata, rresp, rport); \
  u_soc.decode_read(32'h80000000, 3'd4, rdata, rresp, rport); \
  u_soc.decode_read(32'h80000004, 3'd4, rdata, rresp, rport); \
  u_soc.decode_read(32'hC0000000, 3'd4, rdata, rresp, rport); \
  u_soc.decode_read(32'hC0000010, 3'd4, rdata, rresp, rport); \

// Agent expected_for_addr case arms
`define CAMPAIGN_MANIFEST_EXPECT_CASES \
        32'h40000000: expected_for_addr = 32'h00000001; \
        32'h40000004: expected_for_addr = 32'h000000FF; \
        32'h80000000: expected_for_addr = 32'hDEADBEEF; \
        32'h80000004: expected_for_addr = 32'hCAFEBABE; \
        32'hC0000000: expected_for_addr = 32'h00000080; \
        32'hC0000010: expected_for_addr = 32'hDEADDEAD; \

`endif
