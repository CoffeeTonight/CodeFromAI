#include "icode.h"

ICODE_ENTRY(probe_sram_r_02c)
{
    bus_read32(11, 0x8000002Cu);
    vstop();
}
