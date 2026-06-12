# =============================================================================
# VerifCPU Full Campaign Firmware — C build + unified pool image
# =============================================================================
#   make config       # campaign_slots.yaml → manifest, cpus.mk, scale.vh
#   make all          # build + merge hex
# =============================================================================

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

.PHONY: all all-inner clean config soc_init icodes manifest merge hex verify dis soc_cell bus_connect bus_connect_yaml

# Re-invoke after config so cpus.mk / CPU_ACTIVE reflect NUM_SCPU overrides (solo, layout, …)
all: config
	+$(MAKE) all-inner

all-inner: soc_init icodes manifest NOOP $(CPU_ACTIVE) merge
	@echo ""
	@echo "=== Campaign firmware ready ==="
	@ls -la $(BUILD_DIR)/*.bin 2>/dev/null | head -20

# Only pass non-empty overrides — empty NUM_SCPU="" must not mask .bus_layout_stamp
config:
	@set -e; \
	env_args=""; \
	[ -n "$(NUM_SCPU)" ] && env_args="$$env_args NUM_SCPU=$(NUM_SCPU)"; \
	[ -n "$(BUS_LAYOUT)" ] && env_args="$$env_args BUS_LAYOUT=$(BUS_LAYOUT)"; \
	[ -n "$(MASTER_BUS_LAYOUT)" ] && env_args="$$env_args MASTER_BUS_LAYOUT=$(MASTER_BUS_LAYOUT)"; \
	[ -n "$(MASTER_ENABLED)" ] && env_args="$$env_args MASTER_ENABLED=$(MASTER_ENABLED)"; \
	eval "env$$env_args python3 gen_campaign_config.py"

-include cpus.mk
-include cpu_rules.mk
CPU_ACTIVE ?=

soc_init: config
	python3 gen_soc_init.py

manifest: config
	python3 gen_campaign_manifest.py

icodes: config manifest
	python3 build_icode_pool.py

merge: config $(BUILD_DIR)/icode_pool.bin NOOP $(CPU_ACTIVE)
	python3 merge_campaign.py

$(REPO_RTL)/verif_vcpu_soc_cell.v: gen_soc_cell_rtl.py amba_bus_registry.py verilog_paths.py
	python3 gen_soc_cell_rtl.py

soc_cell: $(REPO_RTL)/verif_vcpu_soc_cell.v

$(REPO_INC)/verif_soc_bus_connect.vh: gen_soc_bus_connect.py amba_bus_registry.py verilog_paths.py
	python3 gen_soc_bus_connect.py

bus_connect bus_connect_yaml: $(REPO_INC)/verif_soc_bus_connect.vh

hex: merge

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

dis: all
	@ls -1 $(BUILD_DIR)/*.dis 2>/dev/null | head -20

verify: all
	$(MAKE) -C ../.. full_campaign

clean:
	$(MAKE) -C $(abspath ../..) clean-artifacts