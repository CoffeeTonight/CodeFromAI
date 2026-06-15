# Simple startup for VerifCPU verification firmware
# Sets up stack and jumps to main()

.section .text.startup
.global _start

_start:
    # Set up stack (adjust based on your linker script)
    la sp, _stack_top

    # Call main
    call main

    # If main returns, stop the simulation (using custom vstop)
    .word 0x0000000b          # vstop custom instruction

# Weak default stack (should be overridden by linker script)
.weak _stack_top
_stack_top:
    .word 0