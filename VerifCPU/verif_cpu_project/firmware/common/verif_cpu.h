#ifndef VERIF_CPU_H
#define VERIF_CPU_H

/*
 * Deprecated for campaign firmware — use verif_cpu_verilog/firmware/campaign/include/verif_insns.h
 * (SSOT). Macros below mirror verif_insns.h encoding for non-campaign demos only.
 */

#include <stdint.h>

#define _ENC_CUSTOM(sel, rd, rs1, rs2) \
    (uint32_t)( (((sel) & 0x7Fu) << 25) | (((rs2) & 0x1Fu) << 20) \
               | (((rs1) & 0x1Fu) << 15) | (((rd) & 0x1Fu) << 7) | 0x0Bu )

#define EMIT32(e) __asm__ volatile (".word %0" :: "i"((uint32_t)(e)))

#define vstop()              EMIT32(0x0000000b)
#define vtrace_enter(id)     EMIT32(_ENC_CUSTOM(0x10, id, 0, 0))
#define vtrace_exit(id)      EMIT32(_ENC_CUSTOM(0x11, id, 0, 0))
#define vtrace_log(id)       EMIT32(_ENC_CUSTOM(0x12, id, 0, 0))
#define vsync(id)            EMIT32(_ENC_CUSTOM(0x13, id, 0, 0))
#define vassert_id(id)       EMIT32(_ENC_CUSTOM(0x14, id, 0, 0))
#define vassert_rs1(rs1, id) EMIT32(_ENC_CUSTOM(0x14, id, rs1, 0))
#define vforce(rd, rs2)       EMIT32(_ENC_CUSTOM(0x15, rd, 0, rs2))
#define vrelease(rd)           EMIT32(_ENC_CUSTOM(0x16, rd, 0, 0))
#define vwave(cmd, arg)        EMIT32(_ENC_CUSTOM(0x17, cmd, arg, 0))
#define vhw_force(addr_r, hier_r, val_r) EMIT32(_ENC_CUSTOM(0x18, addr_r, hier_r, val_r))
#define vhw_release(addr_r, hier_r)      EMIT32(_ENC_CUSTOM(0x19, addr_r, hier_r, 0))

#endif /* VERIF_CPU_H */