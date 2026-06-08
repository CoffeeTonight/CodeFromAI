#include "icode.h"

ICODE_ENTRY(probe_sram_r_01c)
{
    bus_read32(11, 0x8000001Cu);
    vstop();
}
