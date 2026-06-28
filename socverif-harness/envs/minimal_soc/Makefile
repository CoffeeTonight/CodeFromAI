TOP ?= tb_minimal_soc
IVFLAGS = -g2012 -I rtl -I tb
include ../common/sim_rules.mk
include ../common/fw_rules.mk

compile:
	@mkdir -p sim_build sim_logs generated/verif
	iverilog $(IVFLAGS) -o sim_build/sim.vvp rtl/periph_soc.v tb/tb_minimal_soc.v

sim: compile
	$(call SIM_RUN,vvp sim_build/sim.vvp,sim_logs/tier0.log)

sim-tier1: fw-run-tier1

sim-tier2: fw-run-tier2

sim-tier3: compile
	iverilog $(IVFLAGS) -DVERIF_TIER3 -o sim_build/sim_t3.vvp rtl/periph_soc.v tb/tb_minimal_soc.v
	$(call SIM_RUN,vvp sim_build/sim_t3.vvp,sim_logs/tier3.log)

fw: fw-compile-tier2

clean:
	rm -rf sim_build sim_logs generated verif_report.json environment_manifest.yaml