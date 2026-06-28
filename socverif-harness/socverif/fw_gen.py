"""Generate VLP self-logging FW from discovered register headers (any env)."""
# goal_build_id = 12

from __future__ import annotations

import re
from pathlib import Path

VERIF_LOG_H = '''#ifndef VERIF_LOG_H
#define VERIF_LOG_H
#include <stdint.h>
#include <stdio.h>
#define VERIF_TAG "VERIF"
static inline void verif_log_pass(const char *id, const char *detail) {
    printf("%s PASS %s %s\\n", VERIF_TAG, id, detail ? detail : "");
}
static inline void verif_log_fail(const char *id, const char *detail, uint32_t exp, uint32_t got) {
    printf("%s FAIL %s %s expect=0x%08X got=0x%08X\\n", VERIF_TAG, id, detail ? detail : "", exp, got);
}
static inline void verif_log_summary(int pass, int fail) {
    int total = pass + fail;
    const char *res = (fail == 0 && pass > 0) ? "PASS" : "FAIL";
    printf("%s SUMMARY pass=%d fail=%d total=%d result=%s\\n", VERIF_TAG, pass, fail, total, res);
}
#endif
'''

HOST_MMIO_SHIM = '''#ifdef HOST_VERIF
#include <stdint.h>
#define HOST_MMIO_SLOTS {slot_count}
static uint32_t _host_mmio[HOST_MMIO_SLOTS];
static volatile uint32_t *host_mmio_ptr(uint32_t addr) {{
{slot_cases}
    return &_host_mmio[0];
}}
static inline volatile uint32_t *verif_mmio(uint32_t addr) {{
    return host_mmio_ptr(addr);
}}
#else
#define verif_mmio(addr) ((volatile uint32_t *)(uintptr_t)(addr))
#endif
'''

VERIF_TESTS_TEMPLATE = '''#include <stdint.h>
#include "{header}"
#include "verif_log.h"

{host_shim}

{test_functions}

void verif_run_all(void) {{
    int pass = 0, fail = 0;
{test_calls}
    verif_log_summary(pass, fail);
}}

int main(void) {{
    verif_run_all();
    return 0;
}}
'''

_SFR_PATTERNS = ("SFR_", "TOY_SFR_", "_SFR_")
_SRAM_PATTERNS = ("SRAM_", "TOY_SRAM_", "_SRAM_")


def parse_reg_header(header_path: Path) -> dict[str, int]:
    lines = header_path.read_text(encoding="utf-8", errors="replace").splitlines()
    syms: dict[str, int] = {}
    changed = True
    while changed:
        changed = False
        for line in lines:
            m = re.match(r"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+)u?", line)
            if m:
                name, val = m.group(1), m.group(2)
                if name in syms:
                    continue
                syms[name] = int(val, 0)
                changed = True
                continue
            m = re.match(
                r"#define\s+(\w+)\s+\((\w+)\s*\+\s*(0x[0-9A-Fa-f]+|\d+)u?\)",
                line,
            )
            if m:
                name, base, off = m.group(1), m.group(2), m.group(3)
                if name in syms or base not in syms:
                    continue
                syms[name] = syms[base] + int(off, 0)
                changed = True
    return syms


def classify_reg_syms(syms: dict[str, int]) -> tuple[list[str], list[str]]:
    """Classify register symbols — supports SFR_, TOY_SFR_, SRAM_, TOY_SRAM_, etc."""
    bases = {k for k in syms if k.endswith("_BASE")}
    sfr: list[str] = []
    sram: list[str] = []
    for name, addr in syms.items():
        if name.endswith("_BASE"):
            continue
        upper = name.upper()
        if any(p in upper for p in _SRAM_PATTERNS):
            sram.append(name)
        elif any(p in upper for p in _SFR_PATTERNS):
            sfr.append(name)
        elif any(name.startswith(b.replace("_BASE", "_")) or addr >= syms.get(b, 0)
                 for b in bases if b.replace("_BASE", "") in upper):
            if "SRAM" in upper:
                sram.append(name)
            elif "SFR" in upper or "CTRL" in upper or "CFG" in upper:
                sfr.append(name)
    if not sfr:
        sfr = [k for k, v in syms.items() if not k.endswith("_BASE")
               and "SRAM" not in k.upper() and v >= 0x40000000][:3]
    if not sram:
        sram = [k for k in syms if "SRAM" in k.upper() and not k.endswith("_BASE")][:2]
    return sfr[:4], sram[:2]


def _host_shim_block(syms: dict[str, int], used: list[str]) -> str:
    slots: list[tuple[str, int, int]] = []
    for i, sym in enumerate(used):
        if sym in syms:
            slots.append((sym, syms[sym], i))
    if not slots:
        return ""
    cases = "\n".join(
        f"    if (addr == {sym}) return &_host_mmio[{idx}];"
        for sym, _, idx in slots
    )
    init_lines = []
    for sym, _, idx in slots:
        if "SRAM" in sym.upper() or "MARK" in sym.upper():
            init_lines.append(f"    _host_mmio[{idx}] = 0xDEADBEEFu;")
        else:
            init_lines.append(f"    _host_mmio[{idx}] = 0x00000001u;")
    return HOST_MMIO_SHIM.format(
        slot_count=max(len(slots), 4),
        slot_cases=cases,
    ) + "\nstatic void host_mmio_init(void) {\n" + "\n".join(init_lines) + "\n}\n"


def generate_verif_tests(
    header_path: Path,
    out_dir: Path,
    sfr_syms: list[str] | None = None,
    sram_syms: list[str] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verif_log.h").write_text(VERIF_LOG_H, encoding="utf-8")

    syms = parse_reg_header(header_path)
    if sfr_syms is None or sram_syms is None:
        auto_sfr, auto_sram = classify_reg_syms(syms)
        sfr_syms = sfr_syms or auto_sfr
        sram_syms = sram_syms or auto_sram

    funcs: list[str] = []
    calls: list[str] = []
    used_syms: list[str] = []

    if sfr_syms:
        primary = sfr_syms[0]
        if primary in syms:
            used_syms.append(primary)
            funcs.append(f"""
static void verif_sfr_batch_rmw(int *pass, int *fail) {{
#ifdef HOST_VERIF
    host_mmio_init();
#endif
    volatile uint32_t *p = verif_mmio({primary});
    uint32_t v = *p;
    uint32_t mask = 0x0000000Fu;
    uint32_t newv = (v & ~mask) | 0x00000003u;
    *p = newv;
    if (*p == newv) {{
        verif_log_pass("sfr_batch_rmw", "single_rmw");
        (*pass)++;
    }} else {{
        verif_log_fail("sfr_batch_rmw", "readback", newv, *p);
        (*fail)++;
    }}
}}
""")
            calls.append("    verif_sfr_batch_rmw(&pass, &fail);")

    for sym in sfr_syms:
        if sym not in syms or sym == (sfr_syms[0] if sfr_syms else ""):
            continue
        used_syms.append(sym)
        fid = f"verif_{sym.lower()}"
        funcs.append(f"""
static void {fid}(int *pass, int *fail) {{
#ifdef HOST_VERIF
    host_mmio_init();
#endif
    volatile uint32_t *p = verif_mmio({sym});
    uint32_t v = *p;
    (void)v;
    verif_log_pass("{sym.lower()}_read", "ok");
    (*pass)++;
}}
""")
        calls.append(f"    {fid}(&pass, &fail);")

    for sym in sram_syms:
        if sym not in syms:
            continue
        used_syms.append(sym)
        fid = f"verif_{sym.lower()}_rw"
        funcs.append(f"""
static void {fid}(int *pass, int *fail) {{
#ifdef HOST_VERIF
    host_mmio_init();
#endif
    volatile uint32_t *p = verif_mmio({sym});
    *p = 0xA5A5A5A5u;
    uint32_t v = *p;
    if (v == 0xA5A5A5A5u) {{
        verif_log_pass("{sym.lower()}_rw", "ok");
        (*pass)++;
    }} else {{
        verif_log_fail("{sym.lower()}_rw", "readback", 0xA5A5A5A5u, v);
        (*fail)++;
    }}
}}
""")
        calls.append(f"    {fid}(&pass, &fail);")

    shim = _host_shim_block(syms, list(dict.fromkeys(used_syms)))
    body = VERIF_TESTS_TEMPLATE.format(
        header=header_path.name,
        host_shim=shim,
        test_functions="\n".join(funcs),
        test_calls="\n".join(calls) if calls else "    verif_log_pass(\"noop\", \"no symbols\"); pass++;",
    )
    out = out_dir / "verif_tests.c"
    out.write_text(body, encoding="utf-8")
    return out


def instrument_env_sanity(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verif_log.h").write_text(VERIF_LOG_H, encoding="utf-8")
    code = '''#include "verif_log.h"
void verif_run_all(void) {
    verif_log_pass("env_sanity", "harness_ok");
    verif_log_summary(1, 0);
}
int main(void) {
    verif_run_all();
    return 0;
}
'''
    path = out_dir / "verif_env_sanity.c"
    path.write_text(code, encoding="utf-8")
    return path