/* Per-icode ELF — single entry, max 256 bytes */

OUTPUT_FORMAT("elf32-littleriscv")
OUTPUT_ARCH(riscv)
ENTRY(icode_entry)

MEMORY {
    ICODE (rx) : ORIGIN = 0x00000000, LENGTH = 256
}

SECTIONS {
    .text 0x000 : {
        KEEP(*(.icode.entry))
        KEEP(*(.icode.entry.*))
    } > ICODE
}