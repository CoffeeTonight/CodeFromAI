# goal_build_id = 12 — shared sim/log rules (single-writer via socverif.sim_log)
HARNESS_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
PYTHON ?= python3
export PYTHONPATH := $(HARNESS_ROOT):$(PYTHONPATH)

# $(call SIM_RUN,vvp_invocation,log_path)
define SIM_RUN
	@mkdir -p $(dir $(2))
	$(PYTHON) -m socverif.sim_log run '$(1)' '$(2)'
endef