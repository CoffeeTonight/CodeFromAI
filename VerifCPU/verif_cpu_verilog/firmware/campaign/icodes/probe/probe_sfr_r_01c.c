#include "icode.h"

ICODE_ENTRY(probe_sfr_r_01c)
{
    bus_read32(11, 0x4000001Cu);
    vstop();
}
