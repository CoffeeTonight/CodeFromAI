# Synthetic env — VCS-style scripts referenced, custom log dir (flexibility test)
TOP = tb_syn
include ../common/sim_rules.mk

compile:
	@mkdir -p build logs
	iverilog -g2012 -o build/syn.vvp rtl/dut.v tb/tb_syn.v

sim:
	$(call SIM_RUN,vvp build/syn.vvp,logs/tier0.log)

sim-tier1:
	iverilog -g2012 -DVERIF_TIER1 -o build/syn_t1.vvp rtl/dut.v tb/tb_syn.v
	$(call SIM_RUN,vvp build/syn_t1.vvp,logs/tier1.log)