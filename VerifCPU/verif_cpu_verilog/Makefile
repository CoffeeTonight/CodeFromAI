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

.PHONY: all verify basic rv32i harness soc full_campaign fw clean clean-artifacts

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

sim_build/tb_soc_dut.vvp: $(SOC_RTL) tb/tb_soc_dut.v
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(SOC_RTL) tb/tb_soc_dut.v

GEN_TB = include/tb_full_campaign_gen.vh

FW_VCPU_BIN = firmware/campaign/build/full_campaign_vcpu.bin
FW_ICODE_BIN = firmware/campaign/build/icode_pool.bin
FW_UNIFIED_HEX = firmware/full_campaign_unified.hex
FW_VCPU_HEX = firmware/full_campaign_vcpu.hex

sim_build/tb_full_campaign.vvp: $(FULL_RTL) tb/tb_full_campaign.v $(GEN_TB) $(FW_VCPU_BIN) $(FW_ICODE_BIN) $(FW_VCPU_HEX) $(FW_UNIFIED_HEX)
	@mkdir -p sim_build
	$(IVERILOG) $(IVFLAGS) -o $@ $(FULL_RTL) tb/tb_full_campaign.v

clean:
	rm -rf sim_build

# Remove all verification byproducts (logs, sim, campaign build, merged hex)
clean-artifacts: clean
	rm -rf $(LOG_FULL) logs
	rm -f firmware/full_campaign_unified.hex firmware/full_campaign_vcpu.hex
	$(MAKE) -C firmware/campaign clean