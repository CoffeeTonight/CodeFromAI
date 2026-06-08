#include "icode.h"

ICODE_ENTRY(probe_sram_r_018)
{
    bus_read32(11, 0x80000018u);
    vstop();
}
