#include "icode.h"

ICODE_ENTRY(probe_sram_r_014)
{
    bus_read32(11, 0x80000014u);
    vstop();
}
