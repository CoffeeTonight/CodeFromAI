#include "icode.h"
#include "soc_regs.h"

ICODE_ENTRY(check_sfr_ctrl)
{
    bus_read32(11, SFR_CTRL);
    vstop();
}