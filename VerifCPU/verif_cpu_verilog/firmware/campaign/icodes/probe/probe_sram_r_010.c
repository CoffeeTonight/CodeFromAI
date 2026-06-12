#include "icode.h"

ICODE_ENTRY(probe_sram_r_010)
{
    bus_read32(11, 0x80000010u);
    vstop();
}
