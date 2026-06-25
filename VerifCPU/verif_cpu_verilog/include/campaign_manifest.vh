// Auto-generated from firmware/campaign/include/campaign_manifest.h
`ifndef CAMPAIGN_MANIFEST_VH
`define CAMPAIGN_MANIFEST_VH

`define MANIFEST_SLAVE_COUNT 0

// Master Phase B: inject bus_read per target (TB calls decode_read)
`define CAMPAIGN_MANIFEST_MASTER_LOG \
  $display("SCPU0 (MSTR) > hint slave=MSTR tap=0 addr=0x%08h expect=0x%08h icode=%s", 32'h40000000, 32'h00000001, "check_sfr_ctrl"); \
  $display("SCPU0 (MSTR) > hint slave=MSTR tap=0 addr=0x%08h expect=0x%08h icode=%s", 32'h40000004, 32'h000000FF, "check_sfr_mask"); \

`define CAMPAIGN_MANIFEST_BUS_READS \
  u_soc.decode_read(32'h40000000, 3'd4, rdata, rresp, rport); \
  u_soc.decode_read(32'h40000004, 3'd4, rdata, rresp, rport); \

// Agent expected_for_addr case arms
`define CAMPAIGN_MANIFEST_EXPECT_CASES \
        32'h40000000: expected_for_addr = 32'h00000001; \
        32'h40000004: expected_for_addr = 32'h000000FF; \

`endif
