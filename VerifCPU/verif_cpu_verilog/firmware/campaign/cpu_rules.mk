# Auto-generated cpu_rules.mk — included by firmware/campaign/Makefile

MSTR: $(BUILD_DIR)/MSTR.bin

$(BUILD_DIR)/MSTR.elf: $(COMMON) cpu_sfr/phase_c.c campaign.ld | $(BUILD_DIR)
	@echo "Building MSTR campaign firmware..."
	$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/MSTR_phase_a.o
	$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/MSTR_phase_b.o
	$(CC) $(CFLAGS) -c cpu_sfr/phase_c.c -o $(BUILD_DIR)/MSTR_phase_c.o
	$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/MSTR_phase_a.o $(BUILD_DIR)/MSTR_phase_b.o $(BUILD_DIR)/MSTR_phase_c.o
	$(OBJDUMP) -d $@ > $(BUILD_DIR)/MSTR.dis

$(BUILD_DIR)/MSTR.bin: $(BUILD_DIR)/MSTR.elf
	$(OBJCOPY) -O binary $< $@
	@echo "  -> $@ ($$(wc -c < $@) bytes)"

NOOP: $(BUILD_DIR)/NOOP.bin

$(BUILD_DIR)/NOOP.elf: cpu_generic/noop.c campaign.ld | $(BUILD_DIR)
	@echo "Building NOOP (reserved slots)..."
	$(CC) $(CFLAGS) -c cpu_generic/noop.c -o $(BUILD_DIR)/NOOP_phase_c.o
	$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/NOOP_phase_c.o

$(BUILD_DIR)/NOOP.bin: $(BUILD_DIR)/NOOP.elf
	$(OBJCOPY) -O binary $< $@
