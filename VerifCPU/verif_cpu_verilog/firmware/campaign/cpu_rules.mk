# Auto-generated cpu_rules.mk — included by firmware/campaign/Makefile

SFR: $(BUILD_DIR)/SFR.bin

$(BUILD_DIR)/SFR.elf: $(COMMON) cpu_sfr/phase_c.c cpu_sfr/sync_barrier.c campaign.ld | $(BUILD_DIR)
	@echo "Building SFR campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/SFR_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/SFR_phase_b.o
	$(CC) $(CFLAGS) -c cpu_sfr/phase_c.c -o $(BUILD_DIR)/SFR_phase_c.o
	$(CC) $(CFLAGS) -c cpu_sfr/sync_barrier.c -o $(BUILD_DIR)/SFR_sync.o
	$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/SFR_phase_a.o $(BUILD_DIR)/SFR_phase_b.o $(BUILD_DIR)/SFR_phase_c.o $(BUILD_DIR)/SFR_sync.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/SFR.dis

$(BUILD_DIR)/SFR.bin: $(BUILD_DIR)/SFR.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

SRAM: $(BUILD_DIR)/SRAM.bin

$(BUILD_DIR)/SRAM.elf: $(COMMON) cpu_sram/phase_c.c cpu_sram/sync_barrier.c campaign.ld | $(BUILD_DIR)
	@echo "Building SRAM campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/SRAM_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/SRAM_phase_b.o
	$(CC) $(CFLAGS) -c cpu_sram/phase_c.c -o $(BUILD_DIR)/SRAM_phase_c.o
	$(CC) $(CFLAGS) -c cpu_sram/sync_barrier.c -o $(BUILD_DIR)/SRAM_sync.o
	$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/SRAM_phase_a.o $(BUILD_DIR)/SRAM_phase_b.o $(BUILD_DIR)/SRAM_phase_c.o $(BUILD_DIR)/SRAM_sync.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/SRAM.dis

$(BUILD_DIR)/SRAM.bin: $(BUILD_DIR)/SRAM.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

UART: $(BUILD_DIR)/UART.bin

$(BUILD_DIR)/UART.elf: $(COMMON) cpu_uart/uart_fw.c cpu_uart/sync_barrier.c campaign.ld | $(BUILD_DIR)
	@echo "Building UART campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/UART_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/UART_phase_b.o
	$(CC) $(CFLAGS) -c cpu_uart/uart_fw.c -o $(BUILD_DIR)/UART_phase_c.o
	$(CC) $(CFLAGS) -c cpu_uart/sync_barrier.c -o $(BUILD_DIR)/UART_sync.o
	$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/UART_phase_a.o $(BUILD_DIR)/UART_phase_b.o $(BUILD_DIR)/UART_phase_c.o $(BUILD_DIR)/UART_sync.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/UART.dis

$(BUILD_DIR)/UART.bin: $(BUILD_DIR)/UART.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

NOOP: $(BUILD_DIR)/NOOP.bin

$(BUILD_DIR)/NOOP.elf: cpu_generic/noop.c campaign.ld | $(BUILD_DIR)
	@echo "Building NOOP (reserved slots)..."
	$(CC) $(CFLAGS) -c cpu_generic/noop.c -o $(BUILD_DIR)/NOOP_phase_c.o
	$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/NOOP_phase_c.o

$(BUILD_DIR)/NOOP.bin: $(BUILD_DIR)/NOOP.elf
	$(OBJCOPY) -O binary $< $@
