#include "icode.h"

ICODE_ENTRY(probe_sram_r_008)
{
    bus_read32(11, 0x80000008u);
    vstop();
}
