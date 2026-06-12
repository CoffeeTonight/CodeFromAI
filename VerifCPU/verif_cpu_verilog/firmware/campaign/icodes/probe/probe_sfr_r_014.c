#include "icode.h"

ICODE_ENTRY(probe_sfr_r_014)
{
    bus_read32(11, 0x40000014u);
    vstop();
}
