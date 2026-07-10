#!/usr/bin/env python3
"""
Probe verification icodes with tinyrv — capture first SoC bus R/W per icode.

Modes:
  --verify-50       Synthetic 50-icode regression suite
  (library API)     probe_compiled_bin, merge_icode_pool, emit_icode_map_h
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Optional

# Standalone: verif_cpu_verilog/tools (optional python_model for golden cross-check)
TOOLS_DIR = Path(__file__).resolve().parent
VERILOG_ROOT = TOOLS_DIR.parent
_LEGACY_PY = VERILOG_ROOT.parent / "verif_cpu_project" / "python_model"
HAS_GOLDEN = False
if _LEGACY_PY.is_dir():
    try:
        sys.path.insert(0, str(_LEGACY_PY))
        from verif_cpu.core.cpu import VerifCPU  # noqa: E402,F401
        from verif_cpu.bus.interface import (  # noqa: E402,F401
            BusInterface,
            BusTransaction,
            BusTransferType,
        )
        from verif_cpu.memory.unified_pool import UnifiedFirmwarePool  # noqa: E402,F401
        HAS_GOLDEN = True
    except ImportError:
        pass

# Minimal RV32 + vstop encoders — always available (no python_model)
_OPCODE_LOAD = 0x03
_OPCODE_STORE = 0x23
_OPCODE_OP_IMM = 0x13
_OPCODE_LUI = 0x37
_OPCODE_CUSTOM0 = 0x0B


def _encode_i_type(opcode: int, rd: int, rs1: int, imm: int, funct3: int = 0) -> int:
    imm12 = imm & 0xFFF
    return (
        (imm12 << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _encode_custom(custom_sel: int, rd: int = 0, rs1: int = 0, rs2: int = 0) -> int:
    return (
        ((custom_sel & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((rd & 0x1F) << 7)
        | _OPCODE_CUSTOM0
    )


def encode_addi(rd: int, rs1: int, imm: int) -> int:
    return _encode_i_type(_OPCODE_OP_IMM, rd, rs1, imm, funct3=0)


def encode_lui(rd: int, imm20: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | _OPCODE_LUI


def encode_lw(rd: int, rs1: int, imm: int) -> int:
    return _encode_i_type(_OPCODE_LOAD, rd, rs1, imm, funct3=0x2)


def encode_sw(rs2: int, rs1: int, imm: int) -> int:
    imm12 = imm & 0xFFF
    imm_high = (imm12 >> 5) & 0x7F
    imm_low = imm12 & 0x1F
    return (
        ((imm_high & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | (0x2 << 12)
        | ((imm_low & 0x1F) << 7)
        | _OPCODE_STORE
    )


def encode_vstop() -> int:
    return _encode_custom(0x00)


try:
    import tinyrv as _tinyrv_mod
except ImportError:
    _tinyrv_mod = None  # type: ignore

HAS_TINYRV = _tinyrv_mod is not None
tinyrv = _tinyrv_mod

SOC_MIN = 0x4000_0000
SOC_MAX = 0xD000_0000
MAX_STEPS = 128
PROBE_PAGE_BYTES = 0x1000  # probe page cache: one 4KiB slice covers entry + first bus txn
ICODE_SLOT_SIZE = 0x1000
ICODE_POOL_BASE = 0x1000  # byte offset within icode region (first slot ptr)
LAYOUT_H = VERILOG_ROOT / "firmware" / "campaign" / "include" / "campaign_layout.h"


def pool_word_icode() -> int:
    """Unified pool word address for embedded icode region (SSOT: campaign_layout.h)."""
    if LAYOUT_H.is_file():
        m = re.search(r"#define\s+POOL_WORD_ICODE\s+0x([0-9a-fA-F]+)", LAYOUT_H.read_text(encoding="utf-8"))
        if m:
            return int(m.group(1), 16)
    return 0x1800


OpKind = Literal["R", "W"]


@dataclass(frozen=True)
class IcodeSpec:
    name: str
    bus_addr: int
    op: OpKind
    write_data: int = 0


@dataclass(frozen=True)
class IcodeImage:
    name: str
    pool_ptr: int
    blob: bytes


@dataclass
class ProbeResult:
    name: str
    got_op: Optional[str]
    got_addr: Optional[int]
    steps: int
    error: Optional[str] = None
    expected_addr: Optional[int] = None
    expected_op: Optional[OpKind] = None

    @property
    def ok_vs_expected(self) -> bool:
        if self.expected_addr is None or self.expected_op is None:
            return self.error is None and self.got_op is not None and self.got_addr is not None
        return (
            self.error is None
            and self.got_op == self.expected_op
            and self.got_addr == self.expected_addr
        )


@dataclass(frozen=True)
class IcodeMapEntry:
    name: str
    pool_ptr: int
    bus_addr: int
    bus_op: str
    tap_port: int
    bin_bytes: int


def tap_port_for_addr(addr: int) -> int:
    if 0x4000_0000 <= addr < 0x4000_1000:
        return 0
    if 0x8000_0000 <= addr < 0x8001_0000:
        return 1
    if 0xC000_0000 <= addr < 0xC000_1000:
        return 2
    return 3


def catalog_by_name() -> dict[str, IcodeSpec]:
    return {s.name: s for s in build_catalog_50()}


def manifest_icode_names_hdr(manifest_hdr: Path) -> list[str]:
    """Unique icode names from generated campaign_manifest.h (SSOT parser)."""
    if not manifest_hdr.is_file():
        raise FileNotFoundError(
            f"missing {manifest_hdr} — run make config && make manifest first"
        )
    campaign_dir = manifest_hdr.resolve().parent.parent
    sys.path.insert(0, str(campaign_dir))
    from manifest_h_parser import parse_icode_names  # noqa: E402

    body = manifest_hdr.read_text(encoding="utf-8")
    return parse_icode_names(body)


def manifest_icode_names(slots_yaml: Path) -> list[str]:
    """Legacy: yaml active targets only (ignores NUM_SCPU). Prefer manifest_icode_names_hdr."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML required to read campaign_slots.yaml") from exc

    data = yaml.safe_load(slots_yaml.read_text(encoding="utf-8"))
    seen: set[str] = set()
    names: list[str] = []
    for ent in data.get("active") or []:
        for t in ent.get("targets") or []:
            icode = t.get("icode")
            if not icode or icode in seen:
                continue
            seen.add(icode)
            names.append(icode)
    return names


def build_catalog() -> list[IcodeSpec]:
    """Probe catalog spanning manifest targets + extended SoC map."""
    specs: list[IcodeSpec] = []

    specs.extend([
        IcodeSpec("check_sfr_ctrl", 0x4000_0000, "R"),
        IcodeSpec("check_sfr_mask", 0x4000_0004, "R"),
        IcodeSpec("check_sram_marker", 0x8000_0000, "R"),
        IcodeSpec("check_sram_aux", 0x8000_0004, "R"),
        IcodeSpec("check_uart_baud", 0xC000_0000, "R"),
        IcodeSpec("check_uart_irq", 0xC000_0010, "R"),
    ])

    for off in (0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0xFC):
        specs.append(IcodeSpec(f"probe_sfr_r_{off:03x}", 0x4000_0000 + off, "R"))

    for off in range(0x08, 0x30, 4):
        specs.append(IcodeSpec(f"probe_sram_r_{off:03x}", 0x8000_0000 + off, "R"))

    for i, off in enumerate(range(0x00, 0x20, 4)):
        specs.append(IcodeSpec(f"probe_sram_w_{off:03x}", 0x8000_0000 + off, "W", write_data=0xA000_0000 + i))

    for off in (0x04, 0x08, 0x0C, 0x14, 0x18, 0x1C, 0x20):
        specs.append(IcodeSpec(f"probe_uart_r_{off:03x}", 0xC000_0000 + off, "R"))

    for i, off in enumerate((0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C)):
        specs.append(IcodeSpec(f"probe_uart_w_{off:03x}", 0xC000_0000 + off, "W", write_data=0xB000_0000 + i))

    # Optional regression lock — set PROBE_ICODE_CATALOG_SIZE=N to assert exact count.
    expected_env = os.environ.get("PROBE_ICODE_CATALOG_SIZE", "").strip()
    if expected_env:
        expected = int(expected_env)
        if len(specs) != expected:
            raise RuntimeError(
                f"catalog build error: expected {expected} icodes, got {len(specs)} "
                f"(unset PROBE_ICODE_CATALOG_SIZE or update recipe)"
            )
    return specs


def build_catalog_50() -> list[IcodeSpec]:
    """Backward-compatible alias — catalog size follows recipe, not a fixed 50."""
    return build_catalog()


def _is_soc_addr(addr: int) -> bool:
    return SOC_MIN <= addr < SOC_MAX


def _load_imm32_words(rd: int, value: int) -> list[int]:
    """Emit lui/addi sequence for absolute 32-bit value (load_soc_addr rules)."""
    upper = ((value + 0x800) >> 12) & 0xFFFFF
    base = upper << 12
    lower = value - base
    words = [encode_lui(rd, upper)]
    if lower:
        words.append(encode_addi(rd, rd, lower & 0xFFF))
    return words


def build_icode_firmware(spec: IcodeSpec) -> tuple[bytes, int]:
    words = _load_imm32_words(10, spec.bus_addr)
    if spec.op == "R":
        words.append(encode_lw(5, 10, 0))
    else:
        words.extend(_load_imm32_words(5, spec.write_data))
        words.append(encode_sw(5, 10, 0))
    words.append(encode_vstop())
    blob = b"".join(struct.pack("<I", w) for w in words)
    return blob, 0x1000


class VerifProbeSim(tinyrv.sim):  # type: ignore[misc, valid-type]
    def __init__(self):
        super().__init__(xlen=32, trap_misaligned=False)
        self.first_bus: Optional[tuple[str, int]] = None
        self.stop = False

    def notify_loading(self, addr):
        self._capture("R", addr)

    def notify_stored(self, addr):
        self._capture("W", addr)

    def _capture(self, kind: str, addr: int):
        if self.first_bus is None and _is_soc_addr(addr):
            self.first_bus = (kind, addr)

    def _custom0(self, **_):
        sel = (self.op.data >> 25) & 0x7F
        rd = (self.op.data >> 7) & 0x1F
        rs1 = (self.op.data >> 15) & 0x1F
        if sel == 0x00:
            self.stop = True
        elif sel == 0x14:
            cond = self.x[rs1] if rs1 else rd
            if not cond:
                self.stop = True
        self.pc += 4


def _probe_window(blob: bytes, exec_pc: int = 0) -> bytes:
    """Return one 4KiB page from exec_pc (mmap page-in equivalent for probe)."""
    page_base = exec_pc & ~(PROBE_PAGE_BYTES - 1)
    page_end = page_base + PROBE_PAGE_BYTES
    if len(blob) <= page_end:
        return blob
    return blob[page_base:page_end]


def _run_tinyrv_on_blob(name: str, blob: bytes, exec_pc: int) -> ProbeResult:
    if tinyrv is None:
        return ProbeResult(name, None, None, 0, "tinyrv not installed")

    window = _probe_window(blob, exec_pc)
    rv = VerifProbeSim()
    rv.copy_in(exec_pc, window)
    rv.pc = exec_pc
    steps = 0
    try:
        while steps < MAX_STEPS and not rv.stop and rv.first_bus is None:
            rv.step(trace=False)
            steps += 1
    except Exception as exc:
        return ProbeResult(name, None, None, steps, str(exc))

    if rv.first_bus is None:
        return ProbeResult(name, None, None, steps, "no SoC bus txn")
    op, addr = rv.first_bus
    return ProbeResult(name, op, addr, steps)


def _run_golden_on_blob(name: str, blob: bytes, exec_pc: int) -> ProbeResult:
    if not HAS_GOLDEN:
        return _run_tinyrv_on_blob(name, blob, exec_pc)

    class _StubBus(BusInterface):
        def __init__(self):
            self.first: Optional[tuple[str, int]] = None

        def read(self, address: int, size: int) -> BusTransaction:
            if self.first is None and _is_soc_addr(address):
                self.first = ("R", address)
            return BusTransaction(False, address, 0, size, BusTransferType.SINGLE, resp=0)

        def write(self, address: int, data: int, size: int) -> BusTransaction:
            if self.first is None and _is_soc_addr(address):
                self.first = ("W", address)
            return BusTransaction(True, address, data, size, BusTransferType.SINGLE, resp=0)

    window = _probe_window(blob, exec_pc)
    pool = UnifiedFirmwarePool()
    if exec_pc == 0:
        pool._data = bytearray(window)
        pool._regions = {0: (0, len(window))}
        cpu_pc = 0
    else:
        mem = bytearray(exec_pc + len(window))
        mem[exec_pc : exec_pc + len(window)] = window
        pool._data = mem
        pool._regions = {0: (0, len(mem))}
        cpu_pc = exec_pc

    bus = _StubBus()
    cpu = VerifCPU(0, bus=bus)
    cpu.trace_enabled = False
    cpu.attach_firmware(pool, 0, len(pool._data))
    cpu.pc = cpu_pc

    steps = 0
    while steps < MAX_STEPS and not cpu.request_sim_stop and bus.first is None:
        cpu.step()
        steps += 1

    if bus.first is None:
        return ProbeResult(name, None, None, steps, "no SoC bus txn")
    op, addr = bus.first
    return ProbeResult(name, op, addr, steps)


def probe_compiled_bin(name: str, blob: bytes, exec_pc: int = 0) -> tuple[ProbeResult, ProbeResult]:
    """Probe a compiled icode .bin; returns (tinyrv, golden)."""
    tr = _run_tinyrv_on_blob(name, blob, exec_pc)
    if HAS_GOLDEN:
        gr = _run_golden_on_blob(name, blob, exec_pc)
    else:
        gr = tr
    return tr, gr


def discover_bins(bin_dir: Path) -> list[tuple[str, Path]]:
    pairs = [(p.stem, p) for p in bin_dir.glob("*.bin")]
    pairs.sort(key=lambda x: x[0])
    return pairs


def assign_pool_ptrs(names: list[str], base: int = ICODE_POOL_BASE, slot: int = ICODE_SLOT_SIZE) -> dict[str, int]:
    return {name: base + i * slot for i, name in enumerate(names)}


def merge_icode_pool(images: list[IcodeImage], total_slots: Optional[int] = None) -> bytes:
    if not images:
        return b""
    slots = total_slots or len(images)
    size = ICODE_POOL_BASE + slots * ICODE_SLOT_SIZE
    mem = bytearray(size)
    for img in images:
        end = img.pool_ptr + len(img.blob)
        if end > len(mem):
            raise ValueError(f"icode {img.name} overflows pool (end=0x{end:x})")
        mem[img.pool_ptr : img.pool_ptr + len(img.blob)] = img.blob
    return bytes(mem)


def probe_images(images: list[IcodeImage]) -> list[IcodeMapEntry]:
    entries: list[IcodeMapEntry] = []
    for img in images:
        tr, gr = probe_compiled_bin(img.name, img.blob, exec_pc=img.pool_ptr)
        if tr.error or gr.error:
            raise RuntimeError(f"probe failed for {img.name}: tinyrv={tr.error} golden={gr.error}")
        if tr.got_op != gr.got_op or tr.got_addr != gr.got_addr:
            raise RuntimeError(
                f"probe mismatch for {img.name}: "
                f"tinyrv {tr.got_op}@0x{(tr.got_addr or 0):08x} vs "
                f"golden {gr.got_op}@0x{(gr.got_addr or 0):08x}"
            )
        assert tr.got_addr is not None and tr.got_op is not None
        entries.append(IcodeMapEntry(
            name=img.name,
            pool_ptr=img.pool_ptr,
            bus_addr=tr.got_addr,
            bus_op=tr.got_op,
            tap_port=tap_port_for_addr(tr.got_addr),
            bin_bytes=len(img.blob),
        ))
    return entries


def emit_icode_map_h(path: Path, entries: list[IcodeMapEntry], pool_bytes: int) -> None:
    lines = [
        "/* Auto-generated by build_icode_pool.py — do not edit */",
        "#ifndef ICODE_MAP_H",
        "#define ICODE_MAP_H",
        "",
        "#include <stdint.h>",
        "",
        f"#define ICODE_SLOT_SIZE    0x{ICODE_SLOT_SIZE:08X}u",
        f"#define ICODE_POOL_BASE    0x{ICODE_POOL_BASE:08X}u",
        f"#define ICODE_MAP_COUNT    {len(entries)}u",
        f"#define ICODE_POOL_BYTES   {pool_bytes}u",
        "",
        "typedef struct {",
        "    const char *name;",
        "    uint32_t    pool_ptr;",
        "    uint32_t    bus_addr;",
        "    uint8_t     bus_op;     /* 'R' or 'W' */",
        "    uint8_t     tap_port;",
        "    uint16_t    bin_bytes;",
        "} icode_map_entry_t;",
        "",
        "static const icode_map_entry_t ICODE_MAP[] = {",
    ]
    for e in entries:
        lines.append(
            f'    {{ "{e.name}", 0x{e.pool_ptr:08X}u, 0x{e.bus_addr:08X}u, '
            f"'{e.bus_op}', {e.tap_port}, {e.bin_bytes} }},"
        )
    lines.extend([
        "};",
        "",
        "#endif /* ICODE_MAP_H */",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def emit_icode_map_vh(path: Path, entries: list[IcodeMapEntry], pool_bytes: int) -> None:
    lines = [
        "// Auto-generated by build_icode_pool.py — do not edit",
        "`ifndef ICODE_MAP_VH",
        "`define ICODE_MAP_VH",
        "",
        f"`define ICODE_SLOT_SIZE      32'h{ICODE_SLOT_SIZE:08X}",
        f"`define ICODE_POOL_BASE      32'h{ICODE_POOL_BASE:08X}",
        f"`define ICODE_POOL_WORD_BASE 32'h{pool_word_icode():08X}",
        f"`define ICODE_POOL_BYTES     {pool_bytes}",
        f"`define ICODE_MAP_COUNT      {len(entries)}",
        "",
    ]
    for e in entries:
        safe = e.name.upper()
        lines.append(f"`define ICODE_PTR_{safe} 32'h{e.pool_ptr:08X}")
        lines.append(f"`define ICODE_BUS_{safe} 32'h{e.bus_addr:08X}")
        lines.append(f"`define ICODE_TAP_{safe}  {e.tap_port}")
    lines.extend(["", "`endif", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def emit_icode_bind_vh(path: Path, manifest_hdr: Path, entries: list[IcodeMapEntry]) -> None:
    """Emit per-tap slot icode_ptr macros in campaign_manifest.h target order."""
    by_name = {e.name: e for e in entries}
    body = manifest_hdr.read_text(encoding="utf-8")
    blocks = []
    for m in re.finditer(
        r"static const manifest_target_t (MANIFEST_\w+_TARGETS)\[\] = \{(.*?)\};",
        body,
        re.S,
    ):
        slave_key = m.group(1).replace("MANIFEST_", "").replace("_TARGETS", "")
        for row in re.finditer(
            r'\{\s*[A-Z0-9_]+\s*,\s*0x[0-9a-fA-F]+u?\s*,\s*"([^"]+)"\s*\}',
            m.group(2),
        ):
            icode = row.group(1)
            if icode in by_name:
                blocks.append((slave_key, icode, by_name[icode]))

    lines = [
        "// Auto-generated by build_icode_pool.py — do not edit",
        "`ifndef ICODE_BIND_VH",
        "`define ICODE_BIND_VH",
        "",
    ]
    slot_idx: dict[str, int] = {}
    for slave, icode, ent in blocks:
        si = slot_idx.get(slave, 0)
        lines.append(f"`define ICODE_{slave}_SLOT{si}_PTR 32'h{ent.pool_ptr:08X}")
        lines.append(f"`define ICODE_{slave}_SLOT{si}_NAME \"{icode}\"")
        slot_idx[slave] = si + 1
    lines.extend(["", "`endif", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def emit_icode_map_json(path: Path, entries: list[IcodeMapEntry], pool_bytes: int) -> None:
    payload = {
        "slot_size": ICODE_SLOT_SIZE,
        "pool_base": ICODE_POOL_BASE,
        "pool_bytes": pool_bytes,
        "count": len(entries),
        "entries": [asdict(e) for e in entries],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def probe_with_tinyrv(spec: IcodeSpec) -> ProbeResult:
    fw, base = build_icode_firmware(spec)
    tr = _run_tinyrv_on_blob(spec.name, fw, base)
    tr.expected_addr = spec.bus_addr
    tr.expected_op = spec.op
    return tr


def probe_with_golden(spec: IcodeSpec) -> ProbeResult:
    if not HAS_GOLDEN:
        return probe_with_tinyrv(spec)
    fw, _ = build_icode_firmware(spec)
    gr = _run_golden_on_blob(spec.name, fw, 0)
    gr.expected_addr = spec.bus_addr
    gr.expected_op = spec.op
    return gr


def run_verification(catalog: list[IcodeSpec], verbose: bool = False) -> int:
    print(f"=== probe_icodes: {len(catalog)} icode verification ===\n")

    tiny_ok = gold_ok = agree_ok = 0
    failures: list[str] = []

    for spec in catalog:
        tr = probe_with_tinyrv(spec)
        gr = probe_with_golden(spec)

        t_exp = tr.ok_vs_expected
        g_exp = gr.ok_vs_expected
        agree = (
            tr.error is None
            and gr.error is None
            and tr.got_op == gr.got_op
            and tr.got_addr == gr.got_addr
        )

        tiny_ok += int(t_exp)
        gold_ok += int(g_exp)
        agree_ok += int(agree)

        status = "PASS" if (t_exp and g_exp and agree) else "FAIL"
        if verbose or status == "FAIL":
            print(
                f"  [{status}] {spec.name:24s} "
                f"expect {spec.op}@0x{spec.bus_addr:08x} | "
                f"tinyrv {tr.got_op}@0x{(tr.got_addr or 0):08x} ({tr.steps} steps) | "
                f"golden {gr.got_op}@0x{(gr.got_addr or 0):08x} ({gr.steps} steps)"
            )
            if tr.error:
                print(f"           tinyrv error: {tr.error}")
            if gr.error:
                print(f"           golden error: {gr.error}")

        if not (t_exp and g_exp and agree):
            failures.append(spec.name)

    n = len(catalog)
    print()
    print(f"  tinyrv vs expected : {tiny_ok}/{n}")
    print(f"  golden vs expected : {gold_ok}/{n}")
    print(f"  tinyrv vs golden   : {agree_ok}/{n}")
    overall = tiny_ok == n and gold_ok == n and agree_ok == n
    print(f"\n  OVERALL: {'PASS' if overall else 'FAIL'}")
    if failures:
        print(f"  Failed: {', '.join(failures)}")
    return 0 if overall else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe icode bus addresses with tinyrv")
    parser.add_argument(
        "--verify-catalog", "--verify-50", action="store_true",
        dest="verify_catalog",
        help="Run full probe catalog verification (all entries from build_catalog())",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print every icode result")
    parser.add_argument("--list", action="store_true", help="List catalog entries")
    args = parser.parse_args()

    catalog = build_catalog()

    if args.list:
        for i, s in enumerate(catalog):
            print(f"{i+1:2d}. {s.name:24s} {s.op} 0x{s.bus_addr:08x}")
        return 0

    if args.verify_catalog:
        return run_verification(catalog, verbose=args.verbose)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())