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
from master_config import load_master, master_has_agent, pool_vcpu_regions
from verilog_paths import CAMPAIGN_ROOT as ROOT, INCLUDE_DIR

SLOTS_YAML = Path(ROOT) / "campaign_slots.yaml"
OUT_MANIFEST = Path(ROOT) / "include" / "campaign_manifest.h"
OUT_LAYOUT = Path(ROOT) / "include" / "campaign_layout.h"
OUT_CPUS_MK = Path(ROOT) / "cpus.mk"
OUT_CPU_RULES = Path(ROOT) / "cpu_rules.mk"
OUT_SCALE_VH = Path(INCLUDE_DIR) / "campaign_scale.vh"
OUT_PARAMS_VH = Path(INCLUDE_DIR) / "campaign_params.vh"
OUT_PLATFORM_VH = Path(INCLUDE_DIR) / "campaign_master.vh"
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


def apply_master_bus_layout(master: dict, layout_str: str) -> None:
    """Apply MASTER_BUS_LAYOUT (single segment, count 1) to SCPU0."""
    layout_types: list[str] = []
    for bt, cnt in parse_layout_segment_types(layout_str):
        layout_types.extend([bt] * cnt)
    if len(layout_types) != 1:
        raise ValueError(
            f"MASTER_BUS_LAYOUT must describe exactly one bus port (got {len(layout_types)})"
        )
    bt = layout_types[0]
    master["bus_type"] = bt
    master["bus_port"] = bus_port_for(0, bt)


def load_layout_stamp() -> dict[str, str]:
    if not LAYOUT_STAMP.is_file():
        return {}
    vals: dict[str, str] = {}
    for line in LAYOUT_STAMP.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def env_nonempty(key: str) -> str:
    raw = os.environ.get(key)
    if raw is not None and raw.strip() != "":
        return raw.strip()
    return ""


def env_or_stamp(key: str, stamp: dict[str, str], *, use_stamp: bool = True) -> str:
    """Env wins when non-empty; optionally fall back to .bus_layout_stamp."""
    val = env_nonempty(key)
    if val:
        return val
    if not use_stamp:
        return ""
    return stamp.get(key, "").strip()


def save_layout_stamp(
    num_scpu: int,
    layout: str,
    master_bus: str,
    master_enabled: int,
) -> None:
    LAYOUT_STAMP.write_text(
        "\n".join([
            f"NUM_SCPU={num_scpu}",
            f"BUS_LAYOUT={layout}",
            f"MASTER_BUS_LAYOUT={master_bus}",
            f"MASTER_ENABLED={master_enabled}",
            "",
        ]),
        encoding="utf-8",
    )
    print(f"[config] Saved {LAYOUT_STAMP.name} (NUM_SCPU={num_scpu})")


def emit_params_vh(max_slots: int) -> None:
    lines = [
        "// Auto-generated from gen_campaign_config.py — do not edit",
        "`ifndef CAMPAIGN_PARAMS_VH",
        "`define CAMPAIGN_PARAMS_VH",
        "",
        "// Slave SCPU/VCPU: SCPU1 .. SCPU`CAMPAIGN_NUM_SCPU (SCPU0 master is extra)",
        f"`define CAMPAIGN_NUM_SCPU {max_slots}",
        "",
        "`endif",
        "",
    ]
    OUT_PARAMS_VH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PARAMS_VH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_PARAMS_VH} (CAMPAIGN_NUM_SCPU={max_slots})")


def emit_master_vh(master: dict, num_scpu: int) -> None:
    solo = 1 if num_scpu == 0 else 0
    vcpu = 1 if master.get("vcpu_enabled") else 0
    agent = 1 if master_has_agent(master) else 0
    bt = master.get("bus_type", "task")
    bp = master.get("bus_port", "")
    lines = [
        "// Auto-generated from gen_campaign_config.py — SCPU0 master superset",
        "`ifndef CAMPAIGN_MASTER_VH",
        "`define CAMPAIGN_MASTER_VH",
        "",
        "`define CAMPAIGN_SOLO_MODE " + str(solo),
        "`define CAMPAIGN_MASTER_SUPERSET 1",
        f"`define CAMPAIGN_MASTER_ENABLED {vcpu}",
        f"`define CAMPAIGN_MASTER_VCPU_ENABLED {vcpu}",
        f"`define CAMPAIGN_MASTER_HAS_AGENT {agent}",
        f"`define CAMPAIGN_MASTER_NAME \"{master['name']}\"",
        f"`define CAMPAIGN_MASTER_TAP_PORT {master['tap_port']}",
        f"`define CAMPAIGN_MASTER_POOL_WORD 32'h{master['pool_word']:08X}",
        f"`define CAMPAIGN_MASTER_BUS_TYPE \"{bt}\"",
        f"`define CAMPAIGN_MASTER_BUS_PORT \"{bp}\"",
        "",
        "`endif",
        "",
    ]
    OUT_PLATFORM_VH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PLATFORM_VH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_PLATFORM_VH} (solo={solo} master_vcpu={vcpu})")


def load_slots() -> tuple[int, int, list[dict], dict]:
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
    return max_slots, stride, slots, raw


def emit_manifest(
    slots: list[dict],
    master: dict,
    max_slots: int,
    stride: int,
) -> None:
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
        " * SCPU0 master targets: MANIFEST_MASTER (when master vcpu enabled).",
        " */",
        "",
        f"#define CAMPAIGN_MAX_SLOTS     {max_slots}",
        f"#define MANIFEST_SLAVE_COUNT   {max_slots}",
        f"#define CAMPAIGN_MASTER_PRESENT {1 if master.get('vcpu_enabled') else 0}",
        "",
        "typedef struct {",
        "    const char *name;",
        "    uint8_t     cpu_id;",
        "    uint8_t     tap_port;",
        "    uint32_t    pool_word;",
        "    uint8_t     target_count;",
        "    uint8_t     enabled;",
        "    const char *bus_type;",
        "    const char *bus_port;",
        "} manifest_slave_t;",
        "",
        "typedef struct {",
        "    const char *name;",
        "    uint8_t     cpu_id;",
        "    uint8_t     tap_port;",
        "    uint32_t    pool_word;",
        "    uint8_t     target_count;",
        "    uint8_t     enabled;",
        "    const char *bus_type;",
        "    const char *bus_port;",
        "} manifest_master_t;",
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

    if master.get("vcpu_enabled"):
        mname = master["name"]
        lines.append("static const manifest_master_t MANIFEST_MASTER = {")
        lines.append(
            f'    "{mname}", 0, {master["tap_port"]}, POOL_WORD_MASTER, '
            f'{master["target_count"]}, 1, '
            f'"{master.get("bus_type", "task")}", "{master.get("bus_port", "")}",'
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

    if master.get("vcpu_enabled") and master.get("targets"):
        lines.append(f"static const manifest_target_t MANIFEST_{master['name']}_TARGETS[] = {{")
        for t in master["targets"]:
            lines.append(
                f'    {{ {t["sym"]}, 0x{t["expect"]:08X}u, "{t["icode"]}" }},'
            )
        lines.append("};")
        lines.append("")

    lines.extend(["#endif", ""])
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text("\n".join(lines), encoding="utf-8")
    active_n = sum(1 for s in slots if s["enabled"])
    print(
        f"[config] Wrote {OUT_MANIFEST} ({max_slots} slave slots, "
        f"{active_n} active, master_vcpu={master.get('vcpu_enabled')})"
    )


def emit_layout(slots: list[dict], master: dict, max_slots: int, stride: int) -> None:
    regions = pool_vcpu_regions(max_slots, master)
    icode_word = regions * stride
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
        f"#define POOL_WORD_MASTER  0x{master['pool_word']:04X}u",
        "",
    ]
    for s in slots:
        lines.append(f"#define POOL_WORD_SLOT{s['pool_index']}  0x{s['pool_word']:04X}u")
    lines.append(f"#define POOL_WORD_ICODE   0x{icode_word:04X}u")
    lines.extend(["", "#endif", ""])
    OUT_LAYOUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_LAYOUT} (icode @ word 0x{icode_word:x})")


def emit_scale_vh(slots: list[dict], master: dict, max_slots: int, stride: int) -> None:
    active = [s for s in slots if s["enabled"]]
    regions = pool_vcpu_regions(max_slots, master)
    icode_word = regions * stride
    max_taps = max(3, max_slots, master["tap_port"] + 1 if master_has_agent(master) else 0)
    lines = [
        "// Auto-generated from campaign_slots.yaml",
        "`ifndef CAMPAIGN_SCALE_VH",
        "`define CAMPAIGN_SCALE_VH",
        "",
        "`include \"campaign_master.vh\"",
        "",
        f"`define CAMPAIGN_MAX_SLOTS      {max_slots}",
        f"`define CAMPAIGN_SLAVE_AGENTS_ENABLED {1 if max_slots > 0 else 0}",
        f"`define CAMPAIGN_MAX_TAPS       {max_taps}",
        f"`define CAMPAIGN_ACTIVE_SLOTS   {len(active)}",
        f"`define CAMPAIGN_POOL_WORD_ICODE 32'h{icode_word:08X}",
        f"`define CAMPAIGN_POOL_VCPU_REGIONS {regions}",
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


def emit_cpus_mk(slots: list[dict], master: dict) -> None:
    lines = [
        "# Auto-generated from campaign_slots.yaml — do not edit",
        "# enabled=1: unique firmware; enabled=0: shares NOOP image at build time",
        "",
    ]
    names = []
    if master.get("vcpu_enabled"):
        m = master
        key = f"CPU_{m['name']}"
        names.append(m["name"])
        lines.append(
            f"{key} := name={m['name']} id=0 role={m['role']} "
            f"pool_word=0x{m['pool_word']:04x} enabled=1 "
            f"phase_c={m['phase_c']}"
        )
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
    active = [s["name"] for s in slots if s["enabled"]]
    if master.get("vcpu_enabled"):
        active = [master["name"]] + active
    lines.append(f"CPU_ACTIVE := {' '.join(active)}")
    OUT_CPUS_MK.write_text("\n".join(lines), encoding="utf-8")
    print(f"[config] Wrote {OUT_CPUS_MK}")


def emit_cpu_rules_mk(slots: list[dict], master: dict) -> None:
    """Per-CPU firmware build rules (generated)."""
    lines = [
        "# Auto-generated cpu_rules.mk — included by firmware/campaign/Makefile",
        "",
    ]

    def _emit_cpu_rules(name: str, phase_c: str, role: str) -> None:
        if role == "noop":
            return
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

    if master.get("vcpu_enabled"):
        _emit_cpu_rules(master["name"], master["phase_c"], master["role"])
    for s in slots:
        if s["enabled"] and s["role"] != "noop":
            _emit_cpu_rules(s["name"], s["phase_c"], s["role"])

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


def resolve_master_vcpu_enabled(
    master_en_env: str,
    num_scpu: int,
    raw: dict,
) -> int:
    """MASTER_ENABLED env/stamp overrides yaml; else solo→1, N≥1→0."""
    if master_en_env != "":
        return 0 if master_en_env in ("0", "false", "False") else 1
    ent = raw.get("master") or {}
    enabled_raw = ent.get("enabled")
    if enabled_raw is not None:
        return 1 if bool(enabled_raw) else 0
    return 1 if num_scpu == 0 else 0


def main() -> int:
    yaml_max, stride, slots, raw = load_slots()

    stamp = load_layout_stamp()
    # Explicit NUM_SCPU (e.g. gen 3 after solo) must not reuse solo BUS_LAYOUT stamp
    num_scpu_explicit = env_nonempty("NUM_SCPU") != ""
    use_stamp = not num_scpu_explicit
    num_scpu_env = env_or_stamp("NUM_SCPU", stamp, use_stamp=use_stamp)
    layout_env = env_or_stamp("BUS_LAYOUT", stamp, use_stamp=use_stamp)
    master_bus_env = env_or_stamp("MASTER_BUS_LAYOUT", stamp, use_stamp=use_stamp)
    master_en_env = env_or_stamp("MASTER_ENABLED", stamp, use_stamp=use_stamp)

    max_slots = yaml_max
    if num_scpu_env != "":
        override = int(num_scpu_env)
        if override < 0 or override > 256:
            raise ValueError(f"NUM_SCPU out of range: {override} (allowed 0..256)")
        if override != max_slots:
            dropped = [
                s for s in slots
                if s["enabled"] and s["cpu_id"] > override
            ]
            if dropped:
                detail = ", ".join(
                    f'{s["name"]}(cpu_id={s["cpu_id"]})' for s in dropped
                )
                print(
                    f"[config] WARN NUM_SCPU={override} — dropping active slot(s) "
                    f"above limit: {detail}",
                    file=sys.stderr,
                )
            max_slots = override
            slots = expand_slots_to_max(slots, max_slots, stride)

    master = load_master(raw, num_scpu=max_slots, resolve_addr=resolve_addr)
    master["vcpu_enabled"] = resolve_master_vcpu_enabled(
        master_en_env, max_slots, raw
    )

    if layout_env:
        apply_bus_layout(slots, layout_env, max_slots)
        wired = sum(
            1 for s in slots
            if normalize_bus_type(s.get("bus_type", "task")) not in ("task", "none")
            and s.get("bus_port")
        )
        print(f"[config] BUS_LAYOUT applied — {wired} external slave bus port(s)")

    if master_bus_env:
        apply_master_bus_layout(master, master_bus_env)
        print(
            f"[config] MASTER_BUS_LAYOUT applied — {master['bus_port']} "
            f"({master['bus_type']})"
        )
    elif max_slots == 0 and not master.get("bus_port"):
        apply_master_bus_layout(master, "axi4lite:1")
        print("[config] solo default MASTER_BUS_LAYOUT=axi4lite:1 → S00_AXI")

    if layout_env or master_bus_env or num_scpu_env != "" or num_scpu_explicit:
        save_layout_stamp(
            max_slots,
            layout_env,
            master_bus_env or (
                f"{master.get('bus_type', 'axi4lite')}:1" if max_slots == 0 else ""
            ),
            int(master.get("vcpu_enabled", 0)),
        )

    emit_params_vh(max_slots)
    emit_master_vh(master, max_slots)
    emit_manifest(slots, master, max_slots, stride)
    emit_layout(slots, master, max_slots, stride)
    emit_scale_vh(slots, master, max_slots, stride)
    emit_cpus_mk(slots, master)
    emit_cpu_rules_mk(slots, master)
    active_n = sum(1 for s in slots if s["enabled"])
    if master.get("vcpu_enabled"):
        active_n += 1
    icode_n = sum(len(s["targets"]) for s in slots if s["enabled"])
    if master.get("vcpu_enabled"):
        icode_n += len(master.get("targets") or [])
    solo = max_slots == 0
    print(
        f"[config] summary: NUM_SCPU={max_slots} solo={solo} "
        f"master_vcpu={master.get('vcpu_enabled')} active={active_n} "
        f"icodes={icode_n} (manifest drives TB + icode build)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())