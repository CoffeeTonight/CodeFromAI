# goal_build_id = 12 — host FW compile + VLP run (generated/verif/*.c)
HARNESS_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
PYTHON ?= python3
export PYTHONPATH := $(HARNESS_ROOT):$(PYTHONPATH)

GEN_VERIF ?= generated/verif
FW_CFLAGS ?= -std=c11 -Wall -DHOST_VERIF -I$(GEN_VERIF) -Iinclude

define FW_BUILD
	@mkdir -p sim_build sim_logs $(GEN_VERIF)
	gcc $(FW_CFLAGS) -o $(1) $(2)
endef

fw-compile-tier1:
	$(call FW_BUILD,sim_build/verif_t1,$(GEN_VERIF)/verif_env_sanity.c)

fw-run-tier1: fw-compile-tier1
	$(call SIM_RUN,./sim_build/verif_t1,sim_logs/tier1.log)

fw-compile-tier2:
	$(call FW_BUILD,sim_build/verif_t2,$(GEN_VERIF)/verif_tests.c)

fw-run-tier2: fw-compile-tier2
	$(call SIM_RUN,./sim_build/verif_t2,sim_logs/tier2.log)

fw: fw-compile-tier2