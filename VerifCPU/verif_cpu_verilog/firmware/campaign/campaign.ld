/* Fixed phase entry layout for full campaign (8 KiB per CPU region) */

OUTPUT_FORMAT("elf32-littleriscv")
OUTPUT_ARCH(riscv)
ENTRY(phase_a_entry)

MEMORY {
    REGION (rwx) : ORIGIN = 0x00000000, LENGTH = 0x2000
}

SECTIONS {
    .phase_a 0x000 : {
        KEEP(*(.phase_a.entry))
        KEEP(*(.phase_a.entry.*))
    } > REGION

    .phase_b 0x100 : {
        KEEP(*(.phase_b.entry))
        KEEP(*(.phase_b.entry.*))
    } > REGION

    .phase_c 0x200 : {
        KEEP(*(.phase_c.entry))
        KEEP(*(.phase_c.entry.*))
    } > REGION

    .uart_hang 0xC00 : {
        KEEP(*(.uart_hang.entry))
        KEEP(*(.uart_hang.entry.*))
    } > REGION

    .uart_recover 0xD00 : {
        KEEP(*(.uart_recover.entry))
        KEEP(*(.uart_recover.entry.*))
    } > REGION
}