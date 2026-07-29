# =============================================================================
# VerifCPU Full Campaign Firmware — C build + unified pool image
# =============================================================================
#   make config       # campaign_slots.yaml → manifest, cpus.mk, scale.vh
#   make gen          # one-shot: config once + firmware + tb_gen + bus_connect
#   make all          # config once + firmware bins + merge hex
#
# gen/all re-invoke make after config so cpus.mk/CPU_ACTIVE pick up NUM_SCPU
# overrides. Downstream targets (soc_init/icodes/merge) must NOT depend on the
# phony `config` target — that re-ran discover+config on every step and made
# `example.py gen 0` look like an infinite loop.
# =============================================================================

.DELETE_ON_ERROR:

CROSS_COMPILE ?= riscv64-unknown-elf-
CC      := $(CROSS_COMPILE)gcc
LD      := $(CROSS_COMPILE)ld
OBJCOPY := $(CROSS_COMPILE)objcopy
OBJDUMP := $(CROSS_COMPILE)objdump

CFLAGS  := -march=rv32i -mabi=ilp32 -Os -Wall -Wextra -ffreestanding -nostdlib \
           -Iinclude -fno-builtin -fno-pic
LDFLAGS := -nostdlib -T campaign.ld

BUILD_DIR := build
COMMON    := common/phase_a.c common/phase_b.c
REPO_RTL  := $(abspath ../../rtl)
REPO_INC  := $(abspath ../../include)

# Chip-specific hierarchy SSOT (copy from soc_hierarchy_example.yaml — do not edit example in place)
HIER_YAML ?= soc_hierarchy_from_slots.yaml
export HIER_YAML

# bus_connect is a phony alias; real artifact is verif_soc_bus_connect.vh (file rule below)
.PHONY: all all-inner gen clean config discover soc_init icodes tb_gen tb_only manifest merge hex verify dis soc_cell bus_connect bus_connect_yaml chip_top_gen integration_gen

# Re-invoke after config so cpus.mk / CPU_ACTIVE reflect NUM_SCPU overrides (solo, layout, …)
all: config
	+$(MAKE) all-inner

# One-shot gen path for example.py / example.sh (config once, no nested re-config)
gen: config
	+$(MAKE) all-inner
	+$(MAKE) tb_only bus_connect

# Do NOT depend on phony `config` here — see header comment.
all-inner: soc_init icodes manifest NOOP $(CPU_ACTIVE) merge
	@echo ""
	@echo "=== Campaign firmware ready ==="
	@ls -la $(BUILD_DIR)/*.bin 2>/dev/null | head -20

discover: discover_campaign_slots.py campaign_slots.yaml
	python3 discover_campaign_slots.py

# Only pass non-empty overrides — empty NUM_SCPU="" must not mask .bus_layout_stamp
config: discover
	@( \
	  [ -z "$(NUM_SCPU)" ] || export NUM_SCPU="$(NUM_SCPU)"; \
	  [ -z "$(BUS_LAYOUT)" ] || export BUS_LAYOUT="$(BUS_LAYOUT)"; \
	  [ -z "$(MASTER_BUS_LAYOUT)" ] || export MASTER_BUS_LAYOUT="$(MASTER_BUS_LAYOUT)"; \
	  [ -z "$(MASTER_ENABLED)" ] || export MASTER_ENABLED="$(MASTER_ENABLED)"; \
	  python3 gen_campaign_config.py \
	)

-include cpus.mk
-include cpu_rules.mk
CPU_ACTIVE ?=

# File-backed steps (phony aliases always run once per goal, but no longer re-config)
soc_init:
	@test -f include/campaign_manifest.h || { echo "ERROR: run 'make config' first"; exit 1; }
	python3 gen_soc_init.py

manifest:
	@test -f include/campaign_manifest.h || { echo "ERROR: run 'make config' first"; exit 1; }
	python3 gen_campaign_manifest.py

# Pool + map/bind only (no TB gen side-effect)
icodes: manifest
	python3 build_icode_pool.py

# Standalone: rebuild pool then TB VH (used outside `make gen`)
tb_gen: icodes gen_tb_campaign.py
	python3 gen_tb_campaign.py --yaml $(HIER_YAML)

# After all-inner (icode_pool already built) — avoids re-running phony icodes
tb_only: gen_tb_campaign.py
	@test -f $(BUILD_DIR)/icode_pool.bin || { \
	  echo "ERROR: missing $(BUILD_DIR)/icode_pool.bin — run make icodes first"; exit 1; }
	python3 gen_tb_campaign.py --yaml $(HIER_YAML)

merge: $(BUILD_DIR)/icode_pool.bin NOOP $(CPU_ACTIVE)
	@test -f cpus.mk || { echo "ERROR: run 'make config' first"; exit 1; }
	python3 merge_campaign.py

$(REPO_RTL)/verif_vcpu_soc_cell.v: gen_soc_cell_rtl.py amba_bus_registry.py verilog_paths.py
	python3 gen_soc_cell_rtl.py

soc_cell: $(REPO_RTL)/verif_vcpu_soc_cell.v

# File-rule: regenerates when manifest / generators change
SOC_CONNECT_VH := $(REPO_INC)/verif_soc_bus_connect.vh
BUS_CONNECT_DEPS := gen_soc_bus_connect.py amba_bus_registry.py verilog_paths.py \
	manifest_h_parser.py slave_yaml_parser.py
MANIFEST_H := include/campaign_manifest.h

$(SOC_CONNECT_VH): $(BUS_CONNECT_DEPS) $(MANIFEST_H)
	python3 gen_soc_bus_connect.py

bus_connect: $(SOC_CONNECT_VH)

chip_top_gen: gen_tb_campaign.py $(HIER_YAML)
	python3 gen_tb_campaign.py --yaml $(HIER_YAML)

integration_gen: discover gen_soc_integration_example.py soc_integration_ports.yaml
	python3 gen_soc_integration_example.py

# YAML hierarchy path — still writes verif_soc_bus_connect.vh
bus_connect_yaml: $(BUS_CONNECT_DEPS) $(HIER_YAML)
	python3 gen_soc_bus_connect.py --yaml $(HIER_YAML)

hex: merge

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

dis: all
	@ls -1 $(BUILD_DIR)/*.dis 2>/dev/null | head -20

verify: all
	$(MAKE) -C ../.. full_campaign

clean:
	$(MAKE) -C $(abspath ../..) clean-artifacts