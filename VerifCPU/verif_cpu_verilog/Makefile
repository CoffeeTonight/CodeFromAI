IVERILOG = iverilog
VVP      = vvp
IVFLAGS  = -g2012 -I include

RTL = rtl/verif_cpu_bus.v \
      rtl/verif_cpu_unified_pool.v \
      rtl/verif_cpu_txn_recorder.v \
      rtl/verif_cpu_core.v

SOC_RTL = rtl/simple_soc.v \
          rtl/verif_orchestrator.v \
          rtl/verif_agent.v

FULL_RTL = $(RTL) \
           rtl/verif_soc_bus.v \
           $(SOC_RTL)

CAMPAIGN_FW = $(MAKE) -C firmware/campaign all
VCD_CHK = python3 tools/verify_vcd.py
LOG_FULL = logs/full_campaign
VCD_MAIN = sim_build/tb_full_campaign.vcd

BUS_RTL = rtl/verif_apb2_master.v \
          rtl/verif_apb_master.v \
          rtl/verif_apb4_master.v \
          rtl/verif_apb5_master.v \
          rtl/verif_ahb_lite_master.v \
          rtl/verif_ahb5_lite_master.v \
          rtl/verif_ahb_master.v \
          rtl/verif_axi_lite_master.v \
          rtl/verif_axi_full_master.v \
          rtl/verif_apb2_slave_simple.v \
          rtl/verif_apb_slave_simple.v \
          rtl/verif_ahb_lite_slave_simple.v \
          rtl/verif_axi_full_slave_simple.v

SOC_CELL_RTL = rtl/verif_vcpu_soc_cell.v
SOC_MANIFEST_DEFS = include/tb_soc_manifest_defs.vh
SOC_MANIFEST_GEN = include/tb_soc_manifest_gen.vh
SOC_MANIFEST_DECODE = include/tb_soc_manifest_decode.vh
MANIFEST_BUS_BIND = include/verif_manifest_soc_bus_read.vh include/verif_manifest_soc_bus_write.vh
CHIP_BUS_BIND = include/verif_chip_soc_bus_read.vh include/verif_chip_soc_bus_write.vh
CHIP_TOP_GEN = include/chip_top_example_gen.vh
CHIP_DECODE = include/chip_top_decode.vh
SOC_CONNECT_VH = include/verif_soc_bus_connect.vh

STUB_BUS_RTL = rtl/verif_axistream_master.v \
               rtl/verif_ace_master.v \
               rtl/verif_ace_lite_master.v \
               rtl/verif_chi_master.v \
               rtl/verif_niu_master.v

BUS_LAYOUT_SCALE ?= axi4lite:58,ahb_lite:1,apb3:1
NUM_SCPU_SCALE ?= 60
SOC_MANIFEST_SCALE_DEFS = include/tb_soc_manifest_scale_defs.vh
SOC_MANIFEST_SCALE_GEN = include/tb_soc_manifest_scale_gen.vh
MANIFEST_SCALE_BUS_BIND = include/verif_manifest_scale_soc_bus_read.vh include/verif_manifest_scale_soc_bus_write.vh

.PHONY: all verify basic rv32i harness soc soc-bus soc-bus-all soc-manifest soc-manifest-scale chip-top-example config-scale full_campaign fw clean clean-artifacts

# Authoritative gate: iverilog sim + VCD post-check
verify: full_campaign

all: verify

basic: sim_build/tb_basic.vvp
	$(VVP) sim_build/tb_basic.vvp

rv32i: sim_build/tb_rv32i_demo.vvp
	$(VVP) sim_build/tb_rv32i_demo.vvp

harness: sim_build/tb_verification_harness.vvp
	mkdir -p logs/harness_v
	$(VVP) sim_build/tb_verification_harness.vvp

soc: sim_build/tb_soc_dut.vvp
	$(VVP) sim_build/tb_soc_dut.vvp

soc-bus: sim_build/tb_soc_bus_bridge.vvp
	$(VVP) sim_build/tb_soc_bus_bridge.vvp

soc-bus-all: sim_build/tb_soc_bus_all.vvp
	$(VVP) sim_build/tb_soc_bus_all.vvp
	python3 tools/verify_amba_bus_vcd.py sim_build/tb_soc_bus_all.vcd

soc-bus-vcd: soc-bus soc-bus-all
	python3 tools/verify_amba_bus_vcd.py sim_build/tb_soc_bus_bridge.vcd sim_build/tb_soc_bus_all.vcd

sim_build/tb_soc_bus_bridge.vvp: $(BUS_RTL) tb/tb_soc_bus_bridge.v
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(BUS_RTL) tb/tb_soc_bus_bridge.v

sim_build/tb_soc_bus_all.vvp: $(BUS_RTL) $(STUB_BUS_RTL) tb/tb_soc_bus_all.v
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(BUS_RTL) $(STUB_BUS_RTL) tb/tb_soc_bus_all.v

fw:
	$(CAMPAIGN_FW)

full_campaign: fw sim_build/tb_full_campaign.vvp
	mkdir -p $(LOG_FULL)
	$(VVP) sim_build/tb_full_campaign.vvp
	$(VCD_CHK) $(VCD_MAIN) $(LOG_FULL)/SCPU1.vcd

sim_build/tb_basic.vvp: $(RTL) tb/tb_basic.v
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(RTL) tb/tb_basic.v

sim_build/tb_rv32i_demo.vvp: $(RTL) tb/tb_rv32i_demo.v
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(RTL) tb/tb_rv32i_demo.v

sim_build/tb_verification_harness.vvp: $(RTL) tb/tb_verification_harness.v
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(RTL) tb/tb_verification_harness.v

PARAMS_VH = include/campaign_params.vh
SCALE_VH = include/campaign_scale.vh

sim_build/tb_soc_dut.vvp: $(SOC_RTL) tb/tb_soc_dut.v $(PARAMS_VH) $(SCALE_VH)
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(SOC_RTL) tb/tb_soc_dut.v

GEN_TB = include/tb_full_campaign_gen.vh

FW_VCPU_BIN = firmware/campaign/build/full_campaign_vcpu.bin
FW_ICODE_BIN = firmware/campaign/build/icode_pool.bin
FW_UNIFIED_HEX = firmware/full_campaign_unified.hex
FW_VCPU_HEX = firmware/full_campaign_vcpu.hex

sim_build/tb_full_campaign.vvp: $(FULL_RTL) tb/tb_full_campaign.v $(GEN_TB) $(PARAMS_VH) $(SCALE_VH) $(FW_VCPU_BIN) $(FW_ICODE_BIN) $(FW_VCPU_HEX) $(FW_UNIFIED_HEX)
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(FULL_RTL) tb/tb_full_campaign.v

$(SOC_CELL_RTL):
	$(MAKE) -C firmware/campaign soc_cell

$(SOC_MANIFEST_DEFS) $(SOC_MANIFEST_GEN) $(SOC_MANIFEST_DECODE) $(SOC_MANIFEST_SCALE_DEFS) $(SOC_MANIFEST_SCALE_GEN) $(MANIFEST_BUS_BIND) $(MANIFEST_SCALE_BUS_BIND) $(CHIP_BUS_BIND) $(CHIP_TOP_GEN) $(CHIP_DECODE): firmware/campaign/build/icode_pool.bin
	$(MAKE) -C firmware/campaign icodes

config-scale:
	$(MAKE) -C firmware/campaign config NUM_SCPU=$(NUM_SCPU_SCALE) BUS_LAYOUT="$(BUS_LAYOUT_SCALE)"
	$(MAKE) -C firmware/campaign bus_connect
	$(MAKE) -C firmware/campaign soc_cell

soc-manifest: fw $(SOC_CELL_RTL) $(SOC_MANIFEST_DEFS) $(SOC_MANIFEST_GEN) $(SOC_MANIFEST_DECODE) $(MANIFEST_BUS_BIND)
	$(MAKE) -C firmware/campaign bus_connect
	$(MAKE) sim_build/tb_soc_manifest.vvp
	$(VVP) sim_build/tb_soc_manifest.vvp

soc-manifest-scale: config-scale fw $(SOC_CELL_RTL) $(SOC_MANIFEST_DEFS) $(SOC_MANIFEST_SCALE_DEFS) $(SOC_MANIFEST_SCALE_GEN) $(SOC_MANIFEST_DECODE) $(MANIFEST_SCALE_BUS_BIND) $(SOC_CONNECT_VH)
	$(MAKE) sim_build/tb_soc_manifest_scale.vvp
	$(VVP) sim_build/tb_soc_manifest_scale.vvp

chip-top-example: fw $(SOC_CELL_RTL) $(CHIP_BUS_BIND) $(CHIP_TOP_GEN) $(CHIP_DECODE)
	$(MAKE) -C firmware/campaign bus_connect_yaml
	$(MAKE) sim_build/chip_top_example.vvp
	$(VVP) sim_build/chip_top_example.vvp

MANIFEST_RTL = rtl/verif_cpu_bus.v \
               rtl/verif_cpu_unified_pool.v \
               rtl/verif_cpu_txn_recorder.v \
               rtl/verif_cpu_core.v \
               rtl/verif_orchestrator.v \
               rtl/verif_agent.v

sim_build/tb_soc_manifest.vvp: $(MANIFEST_RTL) $(BUS_RTL) $(SOC_CELL_RTL) tb/tb_soc_manifest.v $(SOC_MANIFEST_DEFS) $(SOC_MANIFEST_GEN) $(SOC_MANIFEST_DECODE) $(MANIFEST_BUS_BIND) include/campaign_manifest.vh include/icode_map.vh $(SOC_CONNECT_VH) $(FW_UNIFIED_HEX)
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -DVERIF_MANIFEST_SOC_TB -s tb_soc_manifest -o $@ $(MANIFEST_RTL) $(BUS_RTL) $(SOC_CELL_RTL) tb/tb_soc_manifest.v

sim_build/tb_soc_manifest_scale.vvp: $(MANIFEST_RTL) $(BUS_RTL) $(SOC_CELL_RTL) tb/tb_soc_manifest_scale.v $(SOC_MANIFEST_DEFS) $(SOC_MANIFEST_SCALE_DEFS) $(SOC_MANIFEST_SCALE_GEN) $(SOC_MANIFEST_DECODE) $(MANIFEST_SCALE_BUS_BIND) include/campaign_manifest.vh include/campaign_params.vh include/icode_map.vh $(SOC_CONNECT_VH) $(FW_UNIFIED_HEX)
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -DVERIF_MANIFEST_SCALE_TB -s tb_soc_manifest_scale -o $@ $(MANIFEST_RTL) $(BUS_RTL) $(SOC_CELL_RTL) tb/tb_soc_manifest_scale.v

CHIP_TOP_RTL = rtl/verif_cpu_bus.v \
               rtl/verif_cpu_unified_pool.v \
               rtl/verif_cpu_txn_recorder.v \
               rtl/verif_cpu_core.v \
               rtl/verif_orchestrator.v \
               rtl/verif_agent.v

sim_build/chip_top_example.vvp: $(CHIP_TOP_RTL) $(BUS_RTL) $(STUB_BUS_RTL) $(SOC_CELL_RTL) tb/chip_top_example.v $(CHIP_TOP_GEN) $(CHIP_DECODE) $(CHIP_BUS_BIND) include/verif_soc_bus_connect.vh $(SCALE_VH) include/campaign_manifest.vh
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -DVERIF_CHIP_SOC_TB -s chip_top_example -o $@ $(CHIP_TOP_RTL) $(BUS_RTL) $(STUB_BUS_RTL) $(SOC_CELL_RTL) tb/chip_top_example.v

clean:
	rm -rf sim_build

# Remove all verification byproducts (logs, sim, campaign build, merged hex)
clean-artifacts: clean
	rm -rf $(LOG_FULL) logs
	rm -f firmware/full_campaign_unified.hex firmware/full_campaign_vcpu.hex
	$(MAKE) -C firmware/campaign clean
	rm -f firmware/campaign/.bus_layout_stamp