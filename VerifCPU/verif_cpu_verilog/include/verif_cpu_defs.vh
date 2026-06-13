// VerifCPU - Non-synthesizable simulation definitions

`ifndef VERIF_CPU_DEFS_VH
`define VERIF_CPU_DEFS_VH

`define CPU_STATE_RUNNING    3'd0
`define CPU_STATE_STALLED    3'd1
`define CPU_STATE_RESET      3'd2
`define CPU_STATE_DUMMY      3'd3
`define CPU_STATE_SYNC_WAIT  3'd4

`define OPCODE_LOAD      7'h03
`define OPCODE_STORE     7'h23
`define OPCODE_BRANCH    7'h63
`define OPCODE_JALR      7'h67
`define OPCODE_JAL       7'h6F
`define OPCODE_OP_IMM    7'h13
`define OPCODE_OP        7'h33
`define OPCODE_LUI       7'h37
`define OPCODE_CUSTOM0   7'h0B

`define VSEL_STOP        7'h00
`define VSEL_WDT_SET     7'h01
`define VSEL_DUMMY_ON    7'h02
`define VSEL_DUMMY_OFF   7'h03
`define VSEL_WDT_PET     7'h04
`define VSEL_TRACE_ENTER 7'h10
`define VSEL_TRACE_EXIT  7'h11
`define VSEL_TRACE_LOG   7'h12
`define VSEL_SYNC        7'h13
`define VSEL_ASSERT      7'h14
`define VSEL_FORCE       7'h15
`define VSEL_RELEASE     7'h16
`define VSEL_WAVE        7'h17
`define VSEL_HW_FORCE    7'h18
`define VSEL_HW_RELEASE  7'h19

`define HW_FORCE_HIER_ANY 32'hFFFF_FFFF

`define TXN_REC_MAX       256
`define INSTR_TRACE_MAX   512
`define FN_STACK_MAX      16
`define FORCED_MEM_MAX    64
`define COV_PC_MAX        512
`define COV_ASSERT_MAX    64
`define WAVE_CHG_MAX      1024

// Wave commands (vwave)
`define WAVE_CMD_OFF       0
`define WAVE_CMD_ON        1
`define WAVE_CMD_DUMP_ALL  2
`define WAVE_CMD_DUMP_SCOPE 3

`endif