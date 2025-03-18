// header/asic_driver.hpp
#include <stdint.h>
typedef struct {
    struct { uint32_t ready : 1; } bits;
} StatusReg;
typedef struct { StatusReg status; } AsicReg;
static AsicReg* asic = (AsicReg*)0xA0000000;
