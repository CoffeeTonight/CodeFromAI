// Included when -DVERIF_MANIFEST_SOC_TB (tb_soc_manifest only)
`ifndef VERIF_MANIFEST_SOC_BUS_MACROS_VH
`define VERIF_MANIFEST_SOC_BUS_MACROS_VH

// CPU_ID 1..3 → g_slv0..g_slv2 (flat named blocks for iverilog XMR)
`define MANIFEST_SOC_BUS_READ(id, a, s, d, r) \
  case ((id)) \
    4'd1: tb_soc_manifest.g_slv0.u_bus.u_bridge.bus_read((a),(s),(d),(r)); \
    4'd2: tb_soc_manifest.g_slv1.u_bus.u_bridge.bus_read((a),(s),(d),(r)); \
    4'd3: tb_soc_manifest.g_slv2.u_bus.u_bridge.bus_read((a),(s),(d),(r)); \
    default: begin (d) = 32'h0; (r) = 2'd2; end \
  endcase

`define MANIFEST_SOC_BUS_WRITE(id, a, d, s, r) \
  case ((id)) \
    4'd1: tb_soc_manifest.g_slv0.u_bus.u_bridge.bus_write((a),(d),(s),(r)); \
    4'd2: tb_soc_manifest.g_slv1.u_bus.u_bridge.bus_write((a),(d),(s),(r)); \
    4'd3: tb_soc_manifest.g_slv2.u_bus.u_bridge.bus_write((a),(d),(s),(r)); \
    default: (r) = 2'd2; \
  endcase

`endif