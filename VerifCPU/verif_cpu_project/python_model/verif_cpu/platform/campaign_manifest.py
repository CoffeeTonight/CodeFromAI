"""Auto-generated from firmware/campaign/include/campaign_manifest.h."""

VERIFY_MANIFEST = [
    {
        "name": "SFR",
        "cpu_id": 1,
        "tap_port": 0,
        "targets": [
            {
                "addr": 0x40000000,
                "expect": 0x00000001,
                "icode": "check_sfr_ctrl",
            },
            {
                "addr": 0x40000004,
                "expect": 0x000000FF,
                "icode": "check_sfr_mask",
            },
        ],
    },
    {
        "name": "SRAM",
        "cpu_id": 2,
        "tap_port": 1,
        "targets": [
            {
                "addr": 0x80000000,
                "expect": 0xDEADBEEF,
                "icode": "check_sram_marker",
            },
            {
                "addr": 0x80000004,
                "expect": 0xCAFEBABE,
                "icode": "check_sram_aux",
            },
        ],
    },
    {
        "name": "UART",
        "cpu_id": 3,
        "tap_port": 2,
        "targets": [
            {
                "addr": 0xC0000000,
                "expect": 0x00000080,
                "icode": "check_uart_baud",
            },
            {
                "addr": 0xC0000010,
                "expect": 0xDEADDEAD,
                "icode": "check_uart_irq",
            },
        ],
    },
]


def hints_for_slave(name: str) -> list[int]:
    """Addresses Master must inject for this slave."""
    for s in VERIFY_MANIFEST:
        if s["name"] == name:
            return [t["addr"] for t in s["targets"]]
    return []


def all_master_hints() -> list[tuple[str, int, int, str]]:
    """(slave_name, addr, expect, icode) in Master injection order."""
    out = []
    for s in VERIFY_MANIFEST:
        for t in s["targets"]:
            out.append((s["name"], t["addr"], t["expect"], t["icode"]))
    return out


def icode_bind_by_tap() -> dict[int, list[str]]:
    return {s['tap_port']: [t['icode'] for t in s['targets']] for s in VERIFY_MANIFEST}
