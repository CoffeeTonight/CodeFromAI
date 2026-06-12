#!/usr/bin/env python3
"""Generate campaign SSOT artifacts from campaign_slots.yaml (up to 60 slots)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from amba_bus_registry import bus_port_for, normalize_bus_type, parse_layout_segment_types
from verilog_paths import CAMPAIGN_ROOT as ROOT, INCLUDE_DIR

SLOTS_YAML = Path(ROOT) / "campaign_slots.yaml"
OUT_MANIFEST = Path(ROOT) / "include" / "campaign_manifest.h"
OUT_LAYOUT = Path(ROOT) / "include" / "campaign_layout.h"
OUT_CPUS_MK = Path(ROOT) / "cpus.mk"
OUT_CPU_RULES = Path(ROOT) / "cpu_rules.mk"
OUT_SCALE_VH = Path(INCLUDE_DIR) / "campaign_scale.vh"
OUT_PARAMS_VH = Path(INCLUDE_DIR) / "campaign_params.vh"
LAYOUT_STAMP = Path(ROOT) / ".bus_layout_stamp"

SYM_ADDR = {
    "SFR_CTRL": 0x40000000,
    "SFR_CFG": 0x40000004,
    "SRAM_MARKER": 0x80000000,
    "SRAM_AUX": 0x80000004,
    "UART_BAUD": 0xC0000000,
    "UART_IRQ_HANG": 0xC0000010,
}

REGION_BYTES = 0x2000
NOOP_PHASE_C = "cpu_generic/noop.c"


def resolve_addr(token: str) -> int:
    token = token.strip()
    if token in SYM_ADDR:
        return SYM_ADDR[token]
    return int(token, 0)


def expand_slots_to_max(slots: list[dict], max_slots: int, stride: int) -> list[dict]:
    """Grow or shrink reserved rows so manifest matches NUM_SCPU / BUS_LAYOUT total."""
    by_id = {s["cpu_id"]: s for s in slots}
    out: list[dict] = []
    for cid in range(1, max_slots + 1):
        if cid in by_id:
            s = dict(by_id[cid])
            s["pool_word"] = (cid - 1) * stride
            s["pool_index"] = cid - 1
            out.append(s)
            continue
        out.append({
            "name": f"RES{cid:02d}",
            "cpu_id": cid,
            "tap_port": cid - 1,
            "enabled": 0,
            "role": "noop",
            "phase_c": NOOP_PHASE_C,
            "bus_type": "task",
            "bus_port": "",
            "pool_word": (cid - 1) * stride,
            "pool_index": cid - 1,
            "target_count": 0,
            "targets": [],
        })
    return out


def apply_bus_layout(slots: list[dict], layout_str: str, max_slots: int) -> None:
    """Assign bus_type/bus_port per cpu_id from BUS_LAYOUT (reserved + unwired actives)."""
    layout_types: list[str] = []
    for bt, cnt in parse_layout_segment_types(layout_str):
        layout_types.extend([bt] * cnt)
    if len(layout_types) != max_slots:
        raise ValueError(
            f"BUS_LAYOUT covers {len(layout_types)} slot(s) but max_slots={max_slots}"
        )
    by_id = {s["cpu_id"]: s for s in slots}
    for cid in range(1, max_slots + 1):
        bt = layout_types[cid - 1]
        s = by_id[cid]
        if s["enabled"] and s.get("bus_port"):
            continue
        s["bus_type"] = bt
        s["bus_port"] = bus_port_for(cid, bt)


def load_layout_stamp() -> tuple[str, str]:
    if not LAYOUT_STAMP.is_file():
        return "", ""
    vals: dict[str, str] = {}
    for line in LAYOUT_STAMP.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals.get("NUM_SCPU", ""), vals.get("BUS_LAYOUT", "")


def save_layout_stamp(num_scpu: int, layout: str) -> None:
    LAYOUT_STAMP.write_text(
        f"NUM_SCPU={num_scpu}\nBUS_LAYOUT={layout}\n",
        encoding="utf-8",
    )
    print(f"[config] Saved {LAYOUT_STAMP.name} (NUM_SCPU={num_scpu})")


def emit_params_vh(max_slots: int) -> None:
    lines = [
        "// Auto-generated from gen_campaign_config.py — do not edit",
        "`ifndef CAMPAIGN_PARAMS_VH",
        "`define CAMPAIGN_PARAMS_VH",
        "",
        "// Slave SCPU/VCPU instances: SCPU1 .. SCPU`CAMPAIGN_NUM_SCPU (SCPU0 master is extra)",
        f"`define CAMPAIGN_NUM_SCPU {max_slots}",
        "",
        "`endif",
        "",
    ]
    OUT_PARAMS_VH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PARAMS_VH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_PARAMS_VH} (CAMPAIGN_NUM_SCPU={max_slots})")


def load_slots() -> tuple[int, int, list[dict]]:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    if not SLOTS_YAML.is_file():
        raise FileNotFoundError(SLOTS_YAML)

    raw = yaml.safe_load(SLOTS_YAML.read_text(encoding="utf-8"))
    max_slots = int(raw.get("max_slots", 60))
    if max_slots < 1 or max_slots > 256:
        raise ValueError(f"max_slots out of range: {max_slots}")
    stride = int(raw.get("pool_word_stride", 0x800))
    active = raw.get("active") or []

    used_ids = set()
    slots: list[dict] = []
    for ent in active:
        cid = int(ent["cpu_id"])
        if cid < 1 or cid > max_slots:
            raise ValueError(f"cpu_id {cid} out of range 1..{max_slots}")
        if cid in used_ids:
            raise ValueError(f"duplicate cpu_id {cid}")
        used_ids.add(cid)
        targets = []
        for t in ent.get("targets") or []:
            sym = t["sym"]
            targets.append({
                "sym": sym,
                "addr": resolve_addr(sym),
                "expect": t["expect"] if isinstance(t["expect"], int) else int(t["expect"], 0),
                "icode": t["icode"],
            })
        slots.append({
            "name": ent["name"],
            "cpu_id": cid,
            "tap_port": int(ent["tap_port"]),
            "enabled": 1,
            "role": ent.get("role", "generic"),
            "phase_c": ent.get("phase_c", NOOP_PHASE_C),
            "bus_type": str(ent.get("bus_type", "task")),
            "bus_port": str(ent.get("bus_port", "") or ""),
            "pool_word": (cid - 1) * stride,
            "pool_index": cid - 1,
            "target_count": len(targets),
            "targets": targets,
        })

    for cid in range(1, max_slots + 1):
        if cid in used_ids:
            continue
        slots.append({
            "name": f"RES{cid:02d}",
            "cpu_id": cid,
            "tap_port": cid - 1,
            "enabled": 0,
            "role": "noop",
            "phase_c": NOOP_PHASE_C,
            "bus_type": "task",
            "bus_port": "",
            "pool_word": (cid - 1) * stride,
            "pool_index": cid - 1,
            "target_count": 0,
            "targets": [],
        })

    slots.sort(key=lambda s: s["cpu_id"])
    active_count = sum(1 for s in slots if s["enabled"])
    return max_slots, stride, slots


def emit_manifest(slots: list[dict], max_slots: int, stride: int) -> None:
    lines = [
        "#ifndef CAMPAIGN_MANIFEST_H",
        "#define CAMPAIGN_MANIFEST_H",
        "",
        "#include <stdint.h>",
        "#include \"soc_regs.h\"",
        "#include \"campaign_layout.h\"",
        "",
        "/* Auto-generated from firmware/campaign/campaign_slots.yaml — do not edit */",
        "/*",
        " * enabled=0 slots are RESERVED: hierarchy/AXI may be wired later.",
        " * Campaign TB does not step those VCPUs; agents see no tap traffic.",
        " */",
        "",
        f"#define CAMPAIGN_MAX_SLOTS     {max_slots}",
        f"#define MANIFEST_SLAVE_COUNT   {max_slots}",
        "",
        "typedef struct {",
        "    const char *name;",
        "    uint8_t     cpu_id;",
        "    uint8_t     tap_port;",
        "    uint32_t    pool_word;",
        "    uint8_t     target_count;",
        "    uint8_t     enabled;",
        "} manifest_slave_t;",
        "",
        "typedef struct {",
        "    uint32_t    bus_addr;",
        "    uint32_t    expect;",
        "    const char *icode;",
        "} manifest_target_t;",
        "",
        f"static const manifest_slave_t MANIFEST_SLAVES[MANIFEST_SLAVE_COUNT] = {{",
    ]
    for s in slots:
        pool_macro = f"POOL_WORD_SLOT{s['pool_index']}"
        bt = s.get("bus_type", "task")
        bp = s.get("bus_port", "")
        lines.append(
            f'    {{ "{s["name"]}", {s["cpu_id"]}, {s["tap_port"]}, '
            f"{pool_macro}, {s['target_count']}, {s['enabled']}, "
            f'"{bt}", "{bp}" }},'
        )
    lines.append("};")
    lines.append("")

    for s in slots:
        if not s["targets"]:
            continue
        lines.append(f"static const manifest_target_t MANIFEST_{s['name']}_TARGETS[] = {{")
        for t in s["targets"]:
            lines.append(
                f'    {{ {t["sym"]}, 0x{t["expect"]:08X}u, "{t["icode"]}" }},'
            )
        lines.append("};")
        lines.append("")

    lines.extend(["#endif", ""])
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_MANIFEST} ({max_slots} slots, "
          f"{sum(1 for s in slots if s['enabled'])} active)")


def emit_layout(slots: list[dict], max_slots: int, stride: int) -> None:
    icode_word = max_slots * stride
    lines = [
        "#ifndef CAMPAIGN_LAYOUT_H",
        "#define CAMPAIGN_LAYOUT_H",
        "",
        "/* Auto-generated from campaign_slots.yaml */",
        "",
        "#define OFF_PHASE_A       0x000u",
        "#define OFF_PHASE_B       0x100u",
        "#define OFF_PHASE_C       0x200u",
        "#define OFF_UART_HANG     0xC00u",
        "#define OFF_UART_RECOVER  0xD00u",
        "",
        f"#define REGION_SIZE       0x{REGION_BYTES:04X}u",
        f"#define POOL_WORD_STRIDE  0x{stride:04X}u",
        "",
    ]
    for s in slots:
        lines.append(f"#define POOL_WORD_SLOT{s['pool_index']}  0x{s['pool_word']:04X}u")
    lines.append(f"#define POOL_WORD_ICODE   0x{icode_word:04X}u")
    lines.extend(["", "#endif", ""])
    OUT_LAYOUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_LAYOUT} (icode @ word 0x{icode_word:x})")


def emit_scale_vh(slots: list[dict], max_slots: int, stride: int) -> None:
    active = [s for s in slots if s["enabled"]]
    icode_word = max_slots * stride
    lines = [
        "// Auto-generated from campaign_slots.yaml",
        "`ifndef CAMPAIGN_SCALE_VH",
        "`define CAMPAIGN_SCALE_VH",
        "",
        f"`define CAMPAIGN_MAX_SLOTS      {max_slots}",
        f"`define CAMPAIGN_MAX_TAPS       {max_slots}",
        f"`define CAMPAIGN_ACTIVE_SLOTS   {len(active)}",
        f"`define CAMPAIGN_POOL_WORD_ICODE 32'h{icode_word:08X}",
        "",
    ]
    for i, s in enumerate(slots):
        lines.append(f"`define CAMPAIGN_SLOT{i}_CPU_ID   {s['cpu_id']}")
        lines.append(f"`define CAMPAIGN_SLOT{i}_TAP_PORT  {s['tap_port']}")
        lines.append(f"`define CAMPAIGN_SLOT{i}_ENABLED  {s['enabled']}")
        lines.append(f"`define CAMPAIGN_SLOT{i}_POOL_WORD 32'h{s['pool_word']:08X}")
        lines.append(f"`define CAMPAIGN_SLOT{i}_ROLE \"{s['role']}\"")
    lines.extend(["", "`endif", ""])
    OUT_SCALE_VH.parent.mkdir(parents=True, exist_ok=True)
    OUT_SCALE_VH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_SCALE_VH}")


def emit_cpus_mk(slots: list[dict]) -> None:
    lines = [
        "# Auto-generated from campaign_slots.yaml — do not edit",
        "# enabled=1: unique firmware; enabled=0: shares NOOP image at build time",
        "",
    ]
    names = []
    for s in slots:
        key = f"CPU_{s['name']}"
        names.append(s["name"])
        lines.append(
            f"{key} := name={s['name']} id={s['cpu_id']} role={s['role']} "
            f"pool_word=0x{s['pool_word']:04x} enabled={s['enabled']} "
            f"phase_c={s['phase_c']}"
        )
    lines.append("")
    lines.append(f"CPU_NAMES := {' '.join(names)}")
    lines.append(f"CPU_ACTIVE := {' '.join(s['name'] for s in slots if s['enabled'])}")
    OUT_CPUS_MK.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_CPUS_MK}")


def emit_cpu_rules_mk(slots: list[dict]) -> None:
    """Per-CPU firmware build rules (generated)."""
    lines = [
        "# Auto-generated cpu_rules.mk — included by firmware/campaign/Makefile",
        "",
    ]
    for s in slots:
        name = s["name"]
        phase_c = s["phase_c"]
        if s["enabled"] and s["role"] != "noop":
            lines.extend([
                f"{name}: $(BUILD_DIR)/{name}.bin",
                "",
                f"$(BUILD_DIR)/{name}.elf: $(COMMON) {phase_c} campaign.ld | $(BUILD_DIR)",
                f'\t@echo "Building {name} campaign firmware..."',
                f"\t$(CC) $(CFLAGS) -c common/phase_a.c -o $(BUILD_DIR)/{name}_phase_a.o",
                f"\t$(CC) $(CFLAGS) -c common/phase_b.c -o $(BUILD_DIR)/{name}_phase_b.o",
                f"\t$(CC) $(CFLAGS) -c {phase_c} -o $(BUILD_DIR)/{name}_phase_c.o",
                f"\t$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/{name}_phase_a.o "
                f"$(BUILD_DIR)/{name}_phase_b.o $(BUILD_DIR)/{name}_phase_c.o",
                f"\t$(OBJDUMP) -d $@ > $(BUILD_DIR)/{name}.dis",
                "",
                f"$(BUILD_DIR)/{name}.bin: $(BUILD_DIR)/{name}.elf",
                f"\t$(OBJCOPY) -O binary $< $@",
                f'\t@echo "  -> $@ ($$(wc -c < $@) bytes)"',
                "",
            ])
    # Single noop image reused by all reserved slots
    lines.extend([
        "NOOP: $(BUILD_DIR)/NOOP.bin",
        "",
        f"$(BUILD_DIR)/NOOP.elf: {NOOP_PHASE_C} campaign.ld | $(BUILD_DIR)",
        '\t@echo "Building NOOP (reserved slots)..."',
        f"\t$(CC) $(CFLAGS) -c {NOOP_PHASE_C} -o $(BUILD_DIR)/NOOP_phase_c.o",
        "\t$(LD) $(LDFLAGS) -o $@ $(BUILD_DIR)/NOOP_phase_c.o",
        "",
        "$(BUILD_DIR)/NOOP.bin: $(BUILD_DIR)/NOOP.elf",
        "\t$(OBJCOPY) -O binary $< $@",
        "",
    ])
    OUT_CPU_RULES.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_CPU_RULES}")


def main() -> int:
    max_slots, stride, slots = load_slots()

    num_scpu_env = os.environ.get("NUM_SCPU", "").strip()
    layout_env = os.environ.get("BUS_LAYOUT", "").strip()
    if not num_scpu_env or not layout_env:
        stamp_num, stamp_layout = load_layout_stamp()
        if not num_scpu_env:
            num_scpu_env = stamp_num
        if not layout_env:
            layout_env = stamp_layout

    if num_scpu_env:
        override = int(num_scpu_env)
        if override < 1 or override > 256:
            raise ValueError(f"NUM_SCPU out of range: {override}")
        if override != max_slots:
            max_slots = override
            slots = expand_slots_to_max(slots, max_slots, stride)

    if layout_env:
        apply_bus_layout(slots, layout_env, max_slots)
        wired = sum(
            1 for s in slots
            if normalize_bus_type(s.get("bus_type", "task")) not in ("task", "none")
            and s.get("bus_port")
        )
        print(f"[config] BUS_LAYOUT applied — {wired} external bus port(s)")
        save_layout_stamp(max_slots, layout_env)

    emit_params_vh(max_slots)
    emit_manifest(slots, max_slots, stride)
    emit_layout(slots, max_slots, stride)
    emit_scale_vh(slots, max_slots, stride)
    emit_cpus_mk(slots)
    emit_cpu_rules_mk(slots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())