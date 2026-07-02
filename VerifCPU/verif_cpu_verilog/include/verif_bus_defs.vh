// VerifCPU external SoC bus protocol helpers
`ifndef VERIF_BUS_DEFS_VH
`define VERIF_BUS_DEFS_VH

`define VERIF_BUS_TASK      0
`define VERIF_BUS_NONE      1
`define VERIF_BUS_AXI4LITE  2
`define VERIF_BUS_AHB_LITE  3
`define VERIF_BUS_APB3      4
// Legacy aliases (manifest / YAML shorthand)
`define VERIF_BUS_AXI  `VERIF_BUS_AXI4LITE
`define VERIF_BUS_AHB  `VERIF_BUS_AHB_LITE
`define VERIF_BUS_APB  `VERIF_BUS_APB3
// Implemented AMBA bridge kinds (see amba_bus_registry.py + verif_vcpu_soc_cell.v)
`define VERIF_BUS_APB2      10
`define VERIF_BUS_APB4      11
`define VERIF_BUS_APB5      12
`define VERIF_BUS_AHB5_LITE 13
`define VERIF_BUS_AHB_FULL  14
`define VERIF_BUS_AXI3FULL  15
`define VERIF_BUS_AXI4FULL  16
`define VERIF_BUS_AXI5FULL  17
// Planned / manifest-only
`define VERIF_BUS_AXIS      20
`define VERIF_BUS_NIU       21

// Agent snoop bundle pulse — pass reg identifiers for valid/wr/addr/data
`define VERIF_SNOOP_PULSE(V, WR, ADDR, DATA, IS_WR, A, D) \
  begin \
    WR = IS_WR; \
    ADDR = A; \
    DATA = D; \
    V = 1'b1; \
    #1 V = 1'b0; \
  end

`endif