// Auto-generated from firmware/campaign/include/soc_init_seq.h
`ifndef SOC_INIT_SEQ_VH
`define SOC_INIT_SEQ_VH

`define SOC_INIT_STEP_COUNT 19

// Include inside simple_soc run_init — uses decode_write/decode_read/r/p/rd
`define SOC_INIT_RUN_STEPS \
  decode_write(32'h40000000, 32'h00000001, 3'd4, r, p); \
  decode_write(32'h40000004, 32'h000000FF, 3'd4, r, p); \
  decode_write(32'h40000008, 32'h00000010, 3'd4, r, p); \
  decode_read(32'h40000000, 3'd4, rd, r, p); \
  if (rd !== 32'h00000001) $display("[SoC] init read mismatch @0x%08h got=0x%08h expect=0x%08h", 32'h40000000, rd, 32'h00000001); \
  decode_write(32'h4000000C, 32'h00000003, 3'd4, r, p); \
  decode_write(32'h40000010, 32'h80000000, 3'd4, r, p); \
  decode_write(32'h40000014, 32'h80001000, 3'd4, r, p); \
  decode_write(32'h40000018, 32'h00000000, 3'd4, r, p); \
  decode_read(32'h40000004, 3'd4, rd, r, p); \
  if (rd !== 32'h000000FF) $display("[SoC] init read mismatch @0x%08h got=0x%08h expect=0x%08h", 32'h40000004, rd, 32'h000000FF); \
  decode_write(32'h4000001C, 32'h0000FFFF, 3'd4, r, p); \
  decode_write(32'h40000020, 32'h0000CAFE, 3'd4, r, p); \
  decode_read(32'h40000020, 3'd4, rd, r, p); \
  if (rd !== 32'h0000CAFE) $display("[SoC] init read mismatch @0x%08h got=0x%08h expect=0x%08h", 32'h40000020, rd, 32'h0000CAFE); \
  decode_write(32'h80000000, 32'hDEADBEEF, 3'd4, r, p); \
  decode_write(32'h80000004, 32'hCAFEBABE, 3'd4, r, p); \
  decode_write(32'hC0000000, 32'h00000080, 3'd4, r, p); \
  decode_write(32'hC0000010, 32'hDEADDEAD, 3'd4, r, p); \
  decode_read(32'hC0000000, 3'd4, rd, r, p); \
  if (rd !== 32'h00000080) $display("[SoC] init read mismatch @0x%08h got=0x%08h expect=0x%08h", 32'hC0000000, rd, 32'h00000080); \
  decode_read(32'hC0000010, 3'd4, rd, r, p); \
  if (rd !== 32'hDEADDEAD) $display("[SoC] init read mismatch @0x%08h got=0x%08h expect=0x%08h", 32'hC0000010, rd, 32'hDEADDEAD); \
  decode_write(32'h40000018, 32'h80000000, 3'd4, r, p); \

`endif
