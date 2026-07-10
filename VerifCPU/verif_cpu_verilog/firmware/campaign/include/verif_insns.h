#ifndef VERIF_INSNS_H
#define VERIF_INSNS_H

#include <stdint.h>

/* custom ID: rd[4:0] + rs1[4:0] as id[9:5] → 10-bit IDs (0..1023); legacy rd-only = 0..31 */
#define _ENC_CUSTOM_ID_LO(id) ((id) & 0x1Fu)
#define _ENC_CUSTOM_ID_HI(id) (((id) >> 5) & 0x1Fu)
#define _ENC_CUSTOM_ID(id)    _ENC_CUSTOM_ID_LO(id)

#define _ENC_CUSTOM(sel, rd, rs1, rs2) \
    (uint32_t)( (((sel) & 0x7Fu) << 25) | (((rs2) & 0x1Fu) << 20) \
               | (((rs1) & 0x1Fu) << 15) | (((rd) & 0x1Fu) << 7) | 0x0Bu )

#define EMIT32(e) __asm__ volatile (".word %0" :: "i"((uint32_t)(e)))

#define vstop()              EMIT32(0x0000000b)
#define vdummy_on()          EMIT32(_ENC_CUSTOM(0x02, 0, 0, 0))
#define vdummy_off()         EMIT32(_ENC_CUSTOM(0x03, 0, 0, 0))
#define vwdt_pet()           EMIT32(_ENC_CUSTOM(0x04, 0, 0, 0))
#define vwdt_set_rs1(r)      EMIT32(_ENC_CUSTOM(0x01, 0, r, 0))
#define vtrace_enter(id)     EMIT32(_ENC_CUSTOM(0x10, _ENC_CUSTOM_ID_LO(id), _ENC_CUSTOM_ID_HI(id), 0))
#define vtrace_exit(id)      EMIT32(_ENC_CUSTOM(0x11, _ENC_CUSTOM_ID_LO(id), _ENC_CUSTOM_ID_HI(id), 0))
#define vtrace_log(id)       EMIT32(_ENC_CUSTOM(0x12, _ENC_CUSTOM_ID_LO(id), _ENC_CUSTOM_ID_HI(id), 0))
#define vsync(id)            EMIT32(_ENC_CUSTOM(0x13, _ENC_CUSTOM_ID_LO(id), _ENC_CUSTOM_ID_HI(id), 0))
#define vassert_id(id)          EMIT32(_ENC_CUSTOM(0x14, _ENC_CUSTOM_ID_LO(id), 0, _ENC_CUSTOM_ID_HI(id)))
#define vassert_rs1(cond_r, id) EMIT32(_ENC_CUSTOM(0x14, _ENC_CUSTOM_ID_LO(id), cond_r, _ENC_CUSTOM_ID_HI(id)))
#define vforce(rd, rs2)      EMIT32(_ENC_CUSTOM(0x15, rd, 0, rs2))
#define vrelease(rd)           EMIT32(_ENC_CUSTOM(0x16, rd, 0, 0))
#define vwave(cmd, arg)        EMIT32(_ENC_CUSTOM(0x17, cmd, arg, 0))
/* rd=bus_addr reg, rs1=hier_id reg, rs2=value reg */
#define vhw_force(addr_r, hier_r, val_r) EMIT32(_ENC_CUSTOM(0x18, addr_r, hier_r, val_r))
#define vhw_release(addr_r, hier_r)      EMIT32(_ENC_CUSTOM(0x19, addr_r, hier_r, 0))

#define rv_addi(rd, rs1, imm) EMIT32( (uint32_t)(((imm) & 0xFFF) << 20) | ((rs1) << 15) | ((rd) << 7) | 0x13u )
#define rv_lui(rd, imm20)     EMIT32( (uint32_t)(((imm20) & 0xFFFFFu) << 12) | ((rd) << 7) | 0x37u )
#define rv_auipc(rd, imm20)   EMIT32( (uint32_t)(((imm20) & 0xFFFFFu) << 12) | ((rd) << 7) | 0x17u )
#define rv_lw(rd, rs1, off)   EMIT32( (uint32_t)(((off) & 0xFFF) << 20) | ((rs1) << 15) | (0x2u << 12) | ((rd) << 7) | 0x03u )
#define rv_sw(rs2, rs1, off)  EMIT32( (uint32_t)((((off) >> 5) & 0x7Fu) << 25) | ((rs2) << 20) | ((rs1) << 15) | (0x2u << 12) | (((off) & 0x1Fu) << 7) | 0x23u )
#define rv_add(rd, rs1, rs2)  EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | ((rd) << 7) | 0x33u )
#define rv_sub(rd, rs1, rs2)  EMIT32( (uint32_t)((0x20u << 25) | ((rs2) << 20) | ((rs1) << 15) | ((rd) << 7) | 0x33u) )
#define rv_and(rd, rs1, rs2)  EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (0x7u << 12) | ((rd) << 7) | 0x33u )
#define rv_or(rd, rs1, rs2)   EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (0x6u << 12) | ((rd) << 7) | 0x33u )
#define rv_xor(rd, rs1, rs2)  EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (0x4u << 12) | ((rd) << 7) | 0x33u )
#define rv_andi(rd, rs1, imm) EMIT32( (uint32_t)(((imm) & 0xFFFu) << 20) | ((rs1) << 15) | (0x7u << 12) | ((rd) << 7) | 0x13u )
#define rv_ori(rd, rs1, imm)  EMIT32( (uint32_t)(((imm) & 0xFFFu) << 20) | ((rs1) << 15) | (0x6u << 12) | ((rd) << 7) | 0x13u )
#define rv_slli(rd, rs1, shamt) EMIT32( (uint32_t)(((shamt) & 0x1Fu) << 20) | ((rs1) << 15) | (1u << 12) | ((rd) << 7) | 0x13u )
#define rv_srli(rd, rs1, shamt) EMIT32( (uint32_t)(((shamt) & 0x1Fu) << 20) | ((rs1) << 15) | (5u << 12) | ((rd) << 7) | 0x13u )
#define rv_srai(rd, rs1, shamt) EMIT32( (uint32_t)((0x20u << 25) | (((shamt) & 0x1Fu) << 20) | ((rs1) << 15) | (5u << 12) | ((rd) << 7) | 0x13u) )
#define rv_slti(rd, rs1, imm)  EMIT32( (uint32_t)(((imm) & 0xFFF) << 20) | ((rs1) << 15) | (2u << 12) | ((rd) << 7) | 0x13u )
#define rv_sltiu(rd, rs1, imm) EMIT32( (uint32_t)(((imm) & 0xFFFu) << 20) | ((rs1) << 15) | (3u << 12) | ((rd) << 7) | 0x13u )
#define rv_sll(rd, rs1, rs2)   EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (1u << 12) | ((rd) << 7) | 0x33u )
#define rv_srl(rd, rs1, rs2)   EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (5u << 12) | ((rd) << 7) | 0x33u )
#define rv_sra(rd, rs1, rs2)   EMIT32( (uint32_t)((0x20u << 25) | ((rs2) << 20) | ((rs1) << 15) | (5u << 12) | ((rd) << 7) | 0x33u) )
#define rv_slt(rd, rs1, rs2)   EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (2u << 12) | ((rd) << 7) | 0x33u )
#define rv_sltu(rd, rs1, rs2)  EMIT32( (uint32_t)((rs2) << 20) | ((rs1) << 15) | (3u << 12) | ((rd) << 7) | 0x33u )
#define rv_beq(rs1, rs2, off) EMIT32( (uint32_t)((((off) >> 12) & 1u) << 31) | ((((off) >> 5) & 0x3Fu) << 25) | ((uint32_t)(rs2) << 20) | ((uint32_t)(rs1) << 15) | ((((off) >> 11) & 1u) << 7) | ((((off) >> 1) & 0xFu) << 8) | 0x63u )
#define rv_jal(rd, off)       EMIT32( (uint32_t)((((off) >> 20) & 1u) << 31) | ((((off) >> 1) & 0x3FFu) << 21) | ((((off) >> 11) & 1u) << 20) | ((((off) >> 12) & 0xFFu) << 12) | ((rd) << 7) | 0x6Fu )
#define rv_jalr(rd, rs1, off)  EMIT32( (uint32_t)(((off) & 0xFFF) << 20) | ((rs1) << 15) | ((rd) << 7) | 0x67u )

#define load_soc_addr(rd, addr) do { \
    rv_lui(rd, ((addr) + 0x800u) >> 12); \
    rv_addi(rd, rd, (int32_t)((addr) - ((((addr) + 0x800u) >> 12) << 12))); \
} while (0)

#endif