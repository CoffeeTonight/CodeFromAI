# Summary of Requests for the Makefile
#
#     Capture Exit Status:
#         Implement a way to catch the exit status of commands (like gcc and hex2bin) to determine if they succeeded or failed.
#
#     Use System Return of Commands:
#         Specifically handle the exit status of the cd command and other tool commands to ensure proper error handling.
#
#     Conditional Actions Based on Exit Status:
#         Perform different actions depending on the success or failure of the commands, using if statements to check the exit status.
#
#     Compile Various Source Files:
#         Compile a list of source files specified in flist.txt, allowing for varying depths and ignoring comments.
#
#     Convert Executables:
#         Use hex2bin to convert the compiled executables into binary format, capturing and handling any errors that occur during the conversion.
#
#     Maintain Clean Rule:
#         Include a clean rule to remove compiled executables and binary files, helping maintain a clean working directory.
#
#     Informative Output:
#         Provide output messages that indicate the success or failure of each operation, including the exit status of failed commands for better debugging.

# Makefile

# Compiler and options
CC = gcc
CFLAGS = -Wall -O2

# Read file paths from flist.txt, ignoring comments
TARGET_FILES = $(filter-out $(wildcard flist.txt//**),$(shell grep -v '^//' flist.txt | grep -v '^\s*$$'))

# Extract just the file names (without directories) to use as targets
TARGETS = $(notdir $(TARGET_FILES))

.PHONY: all clean hex2bin

# Rule to compile each specified file path
all: $(TARGETS) hex2bin

$(TARGETS): %:
	@source_file=$(filter %/$@, $(TARGET_FILES)); \
	if [ -z "$$source_file" ]; then \
		echo "No source file found for target: $@"; \
		exit 1; \
	fi; \
	executable_name=$(basename $@); \
	cd $(dir $$source_file) && { \
		echo "Changing to directory: $$(pwd)"; \
		echo "Compiling $$source_file into $$executable_name"; \
		$(CC) $(CFLAGS) "$$source_file" -o "$$executable_name"; \
		compile_status=$$?; \
		if [ $$compile_status -ne 0 ]; then \
			echo "Compilation failed for $$source_file (exit status: $$compile_status)"; \
			exit $$compile_status;  # Exiting if compilation fails
		else \
			echo "Compilation succeeded for $$source_file"; \
			# Additional actions can go here if the compilation succeeded
		fi; \
	} || echo "Failed to change directory to $(dir $$source_file)"

# Rule to convert each executable to a .bin file using hex2bin
hex2bin: $(TARGETS)
	@echo "Converting executables to .bin files"
	@$(foreach target, $(TARGETS), \
		hex2bin $(basename $(target)) -o $(basename $(target)).bin; \
		hex2bin_status=$$?; \
		if [ $$hex2bin_status -ne 0 ]; then \
			echo "hex2bin conversion failed for $(basename $(target)) (exit status: $$hex2bin_status)"; \
			exit $$hex2bin_status;  # Exiting if hex2bin fails
		else \
			echo "hex2bin conversion succeeded for $(basename $(target))"; \
			# Additional actions can go here if the conversion succeeded
		fi; \
	)

# Clean rule to remove all compiled executables and .bin files
clean:
	rm -f $(basename $(TARGETS)) $(basename $(TARGETS):=.bin)
