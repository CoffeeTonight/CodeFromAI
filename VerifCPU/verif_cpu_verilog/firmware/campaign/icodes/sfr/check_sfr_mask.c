#include "icode.h"
#include "soc_regs.h"

ICODE_ENTRY(check_sfr_mask)
{
    bus_read32(11, SFR_CFG);
    vstop();
}