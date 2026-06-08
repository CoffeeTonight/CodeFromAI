// Platform layout — mirrors python_model verif_cpu/platform/orchestrator.py

`ifndef VERIF_PLATFORM_DEFS_VH
`define VERIF_PLATFORM_DEFS_VH

`define PHASE_INIT    2'd0
`define PHASE_COLLECT 2'd1
`define PHASE_VERIFY  2'd2
`define PHASE_IDLE    2'd3

`define PHASE_A_OFF  32'h00000
`define PHASE_B_OFF  32'h04000
`define PHASE_C_OFF  32'h08000

`define META_LOCAL   32'h1E000
`define CTX_LOCAL    32'h1F000

`define SHARED_FW_BASE  32'h0000_0000
`define PROG_STORE_BASE 32'h0100_0000
`define META_BASE       32'h0200_0000
`define META_STRIDE       32'h0001_0000

`define MAX_SLOTS 8
`define MAX_HINTS 16

`define SLOT_USED 32'h1
`define SLOT_DONE 32'h2

`endif