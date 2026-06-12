#include "icode.h"

ICODE_ENTRY(probe_sfr_r_00c)
{
    bus_read32(11, 0x4000000Cu);
    vstop();
}
