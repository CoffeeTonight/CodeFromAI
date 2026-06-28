TOP = tb_toy
IVFLAGS = -g2012 -I rtl -I tb
include ../common/sim_rules.mk
include ../common/fw_rules.mk

compile:
	@mkdir -p sim_build sim_logs generated/verif
	iverilog $(IVFLAGS) -o sim_build/toy.vvp rtl/toy_periph.v tb/tb_toy.v

sim: compile
	$(call SIM_RUN,vvp sim_build/toy.vvp,sim_logs/tier0.log)

sim-tier1: fw-run-tier1

sim-tier2: fw-run-tier2

fw: fw-compile-tier2

clean:
	rm -rf sim_build sim_logs generated verif_report.json environment_manifest.yaml