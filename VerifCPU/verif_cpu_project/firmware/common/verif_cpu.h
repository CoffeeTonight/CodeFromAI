#ifndef VERIF_CPU_H
#define VERIF_CPU_H

#include <stdint.h>

// Custom verification instructions (using RISC-V custom-0 opcode space)
// These are implemented in the Python golden model.

#define vstop()           asm volatile (".word 0x0000000b")   // vstop (0x00)
#define vtrace_enter(id)  asm volatile (".word (0x0B | ((%0)<<7))" : : "r"(id))  // placeholder
#define vtrace_exit(id)   asm volatile (".word (0x0B | ((%0)<<7))" : : "r"(id))
#define vassert(cond)     asm volatile (".word (0x0B | ((%0)<<7))" : : "r"(cond))
#define vsync(id)         asm volatile (".word (0x0B | ((%0)<<7))" : : "r"(id))
#define vwave(cmd)        asm volatile (".word (0x0B | ((%0)<<7))" : : "r"(cmd))

// For real implementation, better to use proper .insn or inline asm with correct encoding.
// This is a starting point for the verification firmware.

#endif /* VERIF_CPU_H */