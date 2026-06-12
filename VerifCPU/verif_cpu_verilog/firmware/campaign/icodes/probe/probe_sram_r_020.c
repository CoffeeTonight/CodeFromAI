#include "icode.h"

ICODE_ENTRY(probe_sram_r_020)
{
    bus_read32(11, 0x80000020u);
    vstop();
}
