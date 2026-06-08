# =============================================================================
# VerifCPU Full Campaign Firmware — C build + unified pool image
# =============================================================================
#   make all          # build SFR/SRAM/UART bins + merge hex + gen SoC init
#   make verify       # build + iverilog full_campaign
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

include cpus.mk

.PHONY: all clean soc_init icodes manifest merge hex verify dis SFR SRAM UART

all: soc_init icodes manifest SFR SRAM UART merge
	@echo ""
	@echo "=== Campaign firmware ready ==="
	@ls -la $(BUILD_DIR)/*.bin

soc_init:
	python3 gen_soc_init.py

manifest:
	python3 gen_campaign_manifest.py

icodes:
	python3 build_icode_pool.py

merge: icodes SFR SRAM UART
	python3 merge_campaign.py

hex: merge

# --- SFR CPU (phase A/B/C) ---
SFR: $(BUILD_DIR)/SFR.bin

$(BUILD_DIR)/SFR.elf: $(COMMON) cpu_sfr/phase_c.c campaign.ld | $(BUILD_DIR)
	@echo "Building SFR campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/SFR_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/SFR_phase_b.o
	$(CC) $(CFLAGS) -c cpu_sfr/phase_c.c -o $(BUILD_DIR)/SFR_phase_c.o
	$(LD) $(LDFLAGS) -o $@ \
		$(BUILD_DIR)/SFR_phase_a.o $(BUILD_DIR)/SFR_phase_b.o $(BUILD_DIR)/SFR_phase_c.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/SFR.dis

$(BUILD_DIR)/SFR.bin: $(BUILD_DIR)/SFR.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

# --- SRAM CPU ---
SRAM: $(BUILD_DIR)/SRAM.bin

$(BUILD_DIR)/SRAM.elf: $(COMMON) cpu_sram/phase_c.c campaign.ld | $(BUILD_DIR)
	@echo "Building SRAM campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/SRAM_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/SRAM_phase_b.o
	$(CC) $(CFLAGS) -c cpu_sram/phase_c.c -o $(BUILD_DIR)/SRAM_phase_c.o
	$(LD) $(LDFLAGS) -o $@ \
		$(BUILD_DIR)/SRAM_phase_a.o $(BUILD_DIR)/SRAM_phase_b.o $(BUILD_DIR)/SRAM_phase_c.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/SRAM.dis

$(BUILD_DIR)/SRAM.bin: $(BUILD_DIR)/SRAM.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

# --- UART CPU ---
UART: $(BUILD_DIR)/UART.bin

$(BUILD_DIR)/UART.elf: $(COMMON) cpu_uart/uart_fw.c campaign.ld | $(BUILD_DIR)
	@echo "Building UART campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/UART_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/UART_phase_b.o
	$(CC) $(CFLAGS) -c cpu_uart/uart_fw.c -o $(BUILD_DIR)/UART_uart.o
	$(LD) $(LDFLAGS) -o $@ \
		$(BUILD_DIR)/UART_phase_a.o $(BUILD_DIR)/UART_phase_b.o $(BUILD_DIR)/UART_uart.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/UART.dis

$(BUILD_DIR)/UART.bin: $(BUILD_DIR)/UART.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

dis: all
	@ls -1 $(BUILD_DIR)/*.dis

verify: all
	$(MAKE) -C ../.. full_campaign

clean:
	rm -rf $(BUILD_DIR)