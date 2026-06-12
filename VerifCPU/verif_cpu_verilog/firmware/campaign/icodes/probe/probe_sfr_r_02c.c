#include "icode.h"

ICODE_ENTRY(probe_sfr_r_02c)
{
    bus_read32(11, 0x4000002Cu);
    vstop();
}
