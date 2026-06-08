#include "icode.h"

ICODE_ENTRY(probe_sram_r_00c)
{
    bus_read32(11, 0x8000000Cu);
    vstop();
}
