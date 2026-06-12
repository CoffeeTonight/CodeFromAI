#ifndef ICODE_H
#define ICODE_H

#include "verif_insns.h"

/* One icode image — linker entry is always icode_entry */
#define ICODE_ENTRY(name) \
    __attribute__((section(".icode.entry"), used)) \
    void icode_entry(void)

#define bus_read32(rd, addr) do { \
    load_soc_addr(10, (addr)); \
    rv_lw(rd, 10, 0); \
} while (0)

#define bus_write32(rs2, addr) do { \
    load_soc_addr(10, (addr)); \
    rv_sw(rs2, 10, 0); \
} while (0)

#endif