# =============================================================================
# VerifCPU Firmware Build System (Simple & Scalable)
# =============================================================================
# Usage examples:
#   make DMA                    # Build only DMA CPU
#   make SFR                    # Build only SFR CPU
#   make all                    # Build all CPUs defined in cpus.mk
#   make clean
#
# After building, you will get .bin files in build/
# Later you can merge them into one unified memory image using offsets
# from cpus.mk.
# =============================================================================

CROSS_COMPILE ?= riscv64-unknown-elf-
CC       := $(CROSS_COMPILE)gcc
AS       := $(CROSS_COMPILE)as
LD       := $(CROSS_COMPILE)ld
OBJCOPY  := $(CROSS_COMPILE)objcopy

CFLAGS   := -march=rv32i -mabi=ilp32 -Os -Wall -ffreestanding -nostdlib -Icommon
LDFLAGS  := -nostdlib

BUILD_DIR := build

# Include CPU definitions
include cpus.mk

# Extract all CPU names from cpus.mk (lines starting with CPU_)
CPU_NAMES := $(sort $(filter CPU_%, $(.VARIABLES)))

.PHONY: all clean help $(CPU_NAMES)

all: $(CPU_NAMES)
	@echo ""
	@echo "=== All CPUs built successfully ==="
	@ls -1 $(BUILD_DIR)/*.bin 2>/dev/null || echo "No binaries found"

# Generic build rule for each CPU defined in cpus.mk
# We parse the variable like: CPU_DMA := name=DMA id=0 role=... src_dir=... start_offset=...
define BUILD_CPU_RULE
$(1):
	$(eval CPU_VAR := $($(1)))
	$(eval NAME   := $(shell echo '$(CPU_VAR)' | sed -n 's/.*name=\([^ ]*\).*/\1/p'))
	$(eval ID     := $(shell echo '$(CPU_VAR)' | sed -n 's/.*id=\([^ ]*\).*/\1/p'))
	$(eval ROLE   := $(shell echo '$(CPU_VAR)' | sed -n 's/.*role=\([^ ]*\).*/\1/p'))
	$(eval SRC    := $(shell echo '$(CPU_VAR)' | sed -n 's/.*src_dir=\([^ ]*\).*/\1/p'))
	$(eval OFFSET := $(shell echo '$(CPU_VAR)' | sed -n 's/.*start_offset=\([^ ]*\).*/\1/p'))

	@mkdir -p $(BUILD_DIR)
	@echo "========================================"
	@echo "Building CPU: $(1)"
	@echo "  name       = $(NAME)"
	@echo "  id         = $(ID)"
	@echo "  role       = $(ROLE)"
	@echo "  src_dir    = $(SRC)"
	@echo "  offset     = $(OFFSET)"
	@echo "========================================"

	$(CC) $(CFLAGS) -DCPU_ID=$(ID) -DCPU_NAME=\"$(NAME)\" -c common/startup.S -o $(BUILD_DIR)/$(1)_startup.o
	$(CC) $(CFLAGS) -DCPU_ID=$(ID) -DCPU_NAME=\"$(NAME)\" -c $(SRC)/main.c -o $(BUILD_DIR)/$(1)_main.o

	$(LD) $(LDFLAGS) -T $(SRC)/linker.ld \
		$(BUILD_DIR)/$(1)_startup.o $(BUILD_DIR)/$(1)_main.o \
		-o $(BUILD_DIR)/$(1).elf

	$(OBJCOPY) -O binary $(BUILD_DIR)/$(1).elf $(BUILD_DIR)/$(1).bin
	@echo "  -> Generated: $(BUILD_DIR)/$(1).bin"
endef

$(foreach cpu,$(CPU_NAMES),$(eval $(call BUILD_CPU_RULE,$(cpu))))

clean:
	rm -rf $(BUILD_DIR)
	@echo "Build directory cleaned."

help:
	@echo "Available targets:"
	@echo "  make all          - Build all CPUs defined in cpus.mk"
	@echo "  make <CPU_XXX>    - Build specific CPU (e.g. make CPU_DMA)"
	@echo "  make clean"
	@echo ""
	@echo "Defined CPUs:"
	@for cpu in $(CPU_NAMES); do echo "  $$cpu"; done