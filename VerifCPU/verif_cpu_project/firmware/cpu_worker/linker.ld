/* Simple linker script for VerifCPU cpu_main */

ENTRY(_start)

MEMORY
{
    RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 0x10000
}

SECTIONS
{
    .text : {
        *(.text.startup)
        *(.text)
        *(.text.*)
    } > RAM

    .rodata : {
        *(.rodata)
        *(.rodata.*)
    } > RAM

    .data : {
        *(.data)
        *(.data.*)
    } > RAM

    .bss : {
        *(.bss)
        *(.bss.*)
        *(COMMON)
    } > RAM

    . = ALIGN(4);
    _stack_top = . + 0x2000;   /* 8KB stack */
}