#include "icode.h"

ICODE_ENTRY(probe_sfr_r_028)
{
    bus_read32(11, 0x40000028u);
    vstop();
}
