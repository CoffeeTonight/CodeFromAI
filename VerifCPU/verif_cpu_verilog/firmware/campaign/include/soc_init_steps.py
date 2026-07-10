"""Auto-generated from firmware/campaign/include/soc_init_seq.h."""

SOC_INIT_STEPS = [
    ("write", 0x40000000, 0x00000001, 4),
    ("write", 0x40000004, 0x000000FF, 4),
    ("write", 0x40000008, 0x00000010, 4),
    ("read", 0x40000000, 0x00000001, 4),
    ("write", 0x4000000C, 0x00000003, 4),
    ("write", 0x40000010, 0x80000000, 4),
    ("write", 0x40000014, 0x80001000, 4),
    ("write", 0x40000018, 0x00000000, 4),
    ("read", 0x40000004, 0x000000FF, 4),
    ("write", 0x4000001C, 0x0000FFFF, 4),
    ("write", 0x40000020, 0x0000CAFE, 4),
    ("read", 0x40000020, 0x0000CAFE, 4),
    ("write", 0x80000000, 0xDEADBEEF, 4),
    ("write", 0x80000004, 0xCAFEBABE, 4),
    ("write", 0xC0000000, 0x00000080, 4),
    ("write", 0xC0000010, 0xDEADDEAD, 4),
    ("read", 0xC0000000, 0x00000080, 4),
    ("read", 0xC0000010, 0xDEADDEAD, 4),
    ("write", 0x40000018, 0x80000000, 4),
]
