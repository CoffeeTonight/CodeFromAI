# Makefile

# Compiler and options
CC = gcc
CFLAGS = -Wall -O2

# Read file paths from flist.txt, ignoring comments
TARGET_FILES = $(filter-out $(wildcard flist.txt//**),$(shell grep -v '^//' flist.txt | grep -v '^\s*$$'))

# Extract just the file names (without directories) to use as targets
TARGETS = $(notdir $(TARGET_FILES))

# Compile and convert each target file
.PHONY: all clean hex2bin

all: $(TARGETS) hex2bin

# Rule to compile each specified file path, naming the executable after the file name (without extension)
$(TARGETS): %:
	@source_file=$(filter %/$@, $(TARGET_FILES)); \
	if [ -z "$$source_file" ]; then \
		echo "No source file found for target: $@"; \
		exit 1; \
	fi; \
	executable_name=$(basename $@); \
	echo "Compiling $$source_file into $$executable_name"; \
	$(CC) $(CFLAGS) $$source_file -o $$executable_name || True

# Rule to convert each executable to a .bin file using hex2bin
.PHONY: hex2bin
hex2bin: $(TARGETS)
	@echo "Converting executables to .bin files"
	@$(foreach target, $(TARGETS), hex2bin $(basename $(target)) -o $(basename $(target)).bin; )

# Clean rule to remove all compiled executables and .bin files
clean:
	rm -f $(basename $(TARGETS)) $(basename $(TARGETS):=.bin)
