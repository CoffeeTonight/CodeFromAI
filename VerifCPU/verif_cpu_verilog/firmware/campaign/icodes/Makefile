# =============================================================================
# icode build — compile only (pool merge / probe / header: build_icode_pool.py)
# =============================================================================

CAMPAIGN_ROOT := ..
BUILD_DIR     := $(CAMPAIGN_ROOT)/build/icodes
ICODE_MAX     := 256

CROSS_COMPILE ?= riscv64-unknown-elf-
CC      := $(CROSS_COMPILE)gcc
LD      := $(CROSS_COMPILE)ld
OBJCOPY := $(CROSS_COMPILE)objcopy
OBJDUMP := $(CROSS_COMPILE)objdump

CFLAGS  := -march=rv32i -mabi=ilp32 -Os -Wall -Wextra -ffreestanding -nostdlib \
           -I$(CAMPAIGN_ROOT)/include -Iinclude -fno-builtin -fno-pic
LDFLAGS := -nostdlib -T icode.ld

# SOURCES from gen_icodes_c.py (manifest targets only); fallback only if icodes.mk missing
-include icodes.mk
ifneq ($(wildcard icodes.mk),)
SOURCES := $(ICODE_SOURCES)
else
SOURCES := $(shell find . -name '*.c' ! -path './include/*' ! -path './probe/*' | sort)
endif
NAMES   := $(foreach s,$(SOURCES),$(basename $(notdir $(s))))
BINS    := $(addprefix $(BUILD_DIR)/,$(addsuffix .bin,$(NAMES)))

.PHONY: all clean list

all: $(BINS)
	@echo ""
	@echo "=== icode bins ready ($(words $(NAMES)) images) ==="
	@ls -la $(BUILD_DIR)/*.bin

list:
	@printf '%s\n' $(NAMES)

clean:
	rm -rf $(BUILD_DIR)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

define RULE_ICODE
$(BUILD_DIR)/$(1).bin: $(BUILD_DIR)/$(1).elf
	$(OBJCOPY) -O binary $$< $$@
	@SZ=$$(wc -c < "$$@" | tr -d ' '); \
		if [ "$$SZ" -gt $(ICODE_MAX) ]; then \
			echo "ERROR: icode $(1) is $$SZ bytes (max $(ICODE_MAX))"; exit 1; \
		fi; \
		echo "  -> $$@ ($$SZ bytes)"

$(BUILD_DIR)/$(1).elf: $(2) icode.ld | $(BUILD_DIR)
	@echo "Building icode $(1)..."
	$(CC) $(CFLAGS) -c $(2) -o $(BUILD_DIR)/$(1).o
	$(LD) $(LDFLAGS) -o $$@ $(BUILD_DIR)/$(1).o
	$(OBJDUMP) -d $$@ > $(BUILD_DIR)/$(1).dis
endef

$(foreach s,$(SOURCES),$(eval $(call RULE_ICODE,$(basename $(notdir $(s))),$(s))))