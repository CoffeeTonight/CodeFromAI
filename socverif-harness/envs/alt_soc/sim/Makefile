TOP = tb_chip
VLOG_SRCS = ../verilog/chip_mem.v tb_chip.v
LOGDIR = ../logs
include ../../common/sim_rules.mk

compile:
	@mkdir -p build $(LOGDIR)
	iverilog -g2012 -o build/chip.vvp $(VLOG_SRCS)

sim: compile
	$(call SIM_RUN,vvp build/chip.vvp,$(LOGDIR)/tier0.log)

sim-tier1: compile
	iverilog -g2012 -DVERIF_TIER1 -o build/chip_t1.vvp $(VLOG_SRCS)
	$(call SIM_RUN,vvp build/chip_t1.vvp,$(LOGDIR)/tier1.log)

sim-tier2: compile
	iverilog -g2012 -DVERIF_TIER2 -o build/chip_t2.vvp $(VLOG_SRCS)
	$(call SIM_RUN,vvp build/chip_t2.vvp,$(LOGDIR)/tier2.log)

sim-tier3: compile
	iverilog -g2012 -DVERIF_TIER3 -o build/chip_t3.vvp $(VLOG_SRCS)
	$(call SIM_RUN,vvp build/chip_t3.vvp,$(LOGDIR)/tier3.log)