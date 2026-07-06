#!/usr/bin/env python3
"""Generate tb_full_campaign_gen.vh from cpus.mk + campaign_manifest.h + icode_map.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from amba_bus_registry import (  # noqa: E402
    ADDR_WIDTH_DEFAULT,
    AXI_ID_WIDTH_DEFAULT,
    AXI_MAX_OUTSTANDING_DEFAULT,
    BUS_TYPES,
    DATA_WIDTH_DEFAULT,
    bus_supports_read_outstanding,
    bus_supports_write_outstanding,
    connect_slv_tag,
)
from verilog_paths import (  # noqa: E402
    BUILD_DIR,
    CAMPAIGN_ROOT as ROOT,
    FIRMWARE_DIR as VERILOG_FW,
    INCLUDE_DIR,
    REPO_ROOT,
    REL_ICODE_POOL,
    REL_UNIFIED_HEX,
    REL_VCPU_HEX,
)

CPUS_MK = os.path.join(ROOT, "cpus.mk")
MANIFEST_HDR = os.path.join(ROOT, "include", "campaign_manifest.h")
ICODE_JSON = os.path.join(ROOT, "include", "icode_map.json")
SOC_HIER_YAML = os.path.join(ROOT, "soc_hierarchy_example.yaml")
OUT_VH = os.path.join(INCLUDE_DIR, "tb_full_campaign_gen.vh")
OUT_SOC_MANIFEST_DEFS_VH = os.path.join(INCLUDE_DIR, "tb_soc_manifest_defs.vh")
OUT_SOC_MANIFEST_VH = os.path.join(INCLUDE_DIR, "tb_soc_manifest_gen.vh")
OUT_SOC_MANIFEST_SCALE_DEFS_VH = os.path.join(INCLUDE_DIR, "tb_soc_manifest_scale_defs.vh")
OUT_SOC_MANIFEST_SCALE_VH = os.path.join(INCLUDE_DIR, "tb_soc_manifest_scale_gen.vh")
OUT_MANIFEST_BUS_READ_VH = os.path.join(INCLUDE_DIR, "verif_manifest_soc_bus_read.vh")
OUT_MANIFEST_BUS_WRITE_VH = os.path.join(INCLUDE_DIR, "verif_manifest_soc_bus_write.vh")
OUT_MANIFEST_SCALE_BUS_READ_VH = os.path.join(INCLUDE_DIR, "verif_manifest_scale_soc_bus_read.vh")
OUT_MANIFEST_SCALE_BUS_WRITE_VH = os.path.join(INCLUDE_DIR, "verif_manifest_scale_soc_bus_write.vh")
OUT_MANIFEST_DECODE_VH = os.path.join(INCLUDE_DIR, "tb_soc_manifest_decode.vh")
OUT_CHIP_BUS_READ_VH = os.path.join(INCLUDE_DIR, "verif_chip_soc_bus_read.vh")
OUT_CHIP_BUS_WRITE_VH = os.path.join(INCLUDE_DIR, "verif_chip_soc_bus_write.vh")
OUT_CHIP_TOP_RTL_MK = os.path.join(INCLUDE_DIR, "chip_top_rtl.mk")
OUT_CHIP_SOC_CELL = os.path.join(REPO_ROOT, "rtl", "verif_vcpu_soc_cell_chip.v")

CHIP_STUB_BUS_KEYS = frozenset({"ace", "ace_lite", "chi", "niu", "axistream"})
CHIP_MASTER_DEPS: dict[str, list[str]] = {
    "ace": ["verif_axi_full_master"],
}
CHIP_SLAVE_RTL: dict[str, str] = {
    "apb2": "verif_apb2_slave_simple",
    "apb3": "verif_apb_slave_simple",
    "apb4": "verif_apb_slave_simple",
    "apb5": "verif_apb_slave_simple",
    "ahb_lite": "verif_ahb_lite_slave_simple",
    "ahb5_lite": "verif_ahb_lite_slave_simple",
    "ahb": "verif_ahb_lite_slave_simple",
    "axi4lite": "verif_axi_full_slave_simple",
    "axi3full": "verif_axi_full_slave_simple",
    "axi4full": "verif_axi_full_slave_simple",
    "axi5full": "verif_axi_full_slave_simple",
}

OS_BIND_APIS = (
    ("read_issue", "bus_read_issue", "addr, size, handle, ok"),
    ("read_wait", "bus_read_wait", "handle, data, resp"),
    ("read_poll", "bus_read_poll", "handle, data, resp, done"),
    ("write_issue", "bus_write_issue", "addr, data, size, handle, ok"),
    ("write_wait", "bus_write_wait", "handle, resp"),
    ("write_poll", "bus_write_poll", "handle, resp, done"),
    ("read_os_count", "bus_read_outstanding_count", "n"),
    ("write_os_count", "bus_write_outstanding_count", "n"),
)
OUT_CHIP_TOP_GEN_VH = os.path.join(INCLUDE_DIR, "chip_top_example_gen.vh")
OUT_CHIP_DECODE_VH = os.path.join(INCLUDE_DIR, "chip_top_decode.vh")
SOC_INIT_SEQ_VH = os.path.join(INCLUDE_DIR, "soc_init_seq.vh")
ICODE_POOL_BIN = os.path.join(BUILD_DIR, "icode_pool.bin")

from slave_yaml_parser import parse_slave_yaml_ent, require_slave_name_cpu_id  # noqa: E402
from campaign_pool_policy import (  # noqa: E402
    POOL_READMEMH_MAX_BYTES,
    POOL_WORD_ICODE,
    icode_use_lazy,
    max_slots as policy_max_slots,
    unified_mem_words,
)

SCALE_VH = os.path.join(INCLUDE_DIR, "campaign_scale.vh")

SYM_ADDR = {
    "SFR_CTRL": 0x40000000,
    "SFR_CFG": 0x40000004,
    "SRAM_MARKER": 0x80000000,
    "SRAM_AUX": 0x80000004,
    "UART_BAUD": 0xC0000000,
    "UART_IRQ_HANG": 0xC0000010,
}


def resolve_addr(token: str) -> int:
    token = token.strip()
    if token in SYM_ADDR:
        return SYM_ADDR[token]
    return int(token, 0)


def parse_cpus_mk(path: str) -> list[dict]:
    cpus = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or ":=" not in line:
                continue
            if not line.startswith("CPU_") or line.startswith(("CPU_NAMES", "CPU_ACTIVE")):
                continue
            name_m = re.search(r"name=([^\s]+)", line)
            id_m = re.search(r"id=(\d+)", line)
            pool_m = re.search(r"pool_word=(0x[0-9a-fA-F]+)", line)
            if not (name_m and id_m and pool_m):
                continue
            en = re.search(r"enabled=([01])", line)
            role_m = re.search(r"role=([^\s]+)", line)
            cpus.append({
                "name": name_m.group(1),
                "id": int(id_m.group(1)),
                "role": role_m.group(1) if role_m else "generic",
                "pool_word": int(pool_m.group(1), 16),
                "enabled": int(en.group(1)) if en else 1,
            })
    cpus.sort(key=lambda c: c["id"])
    return cpus


CAMPAIGN_SYNC_BARRIER_ID = 10


def sync_participant_mask(cpus: list[dict]) -> int:
    mask = 0
    for c in cpus:
        mask |= 1 << (c["id"] - 1)
    return mask


def cpu_hdl(cpu_id: int) -> str:
    if cpu_id == 0:
        return "u_mstr_cpu"
    return f"g_cpu[{cpu_id - 1}].u_cpu"


def cpu_hierarchy_hex(cpu_id: int) -> str:
    return f"32'h{(cpu_id * 0x10):08X}"


def agent_hdl(cpu_id: int) -> str:
    if cpu_id == 0:
        return "u_mstr_ag"
    return f"g_ag[{cpu_id - 1}].u_ag"


def agent_pass_ref(cpu_id: int) -> str:
    if cpu_id == 0:
        return "mstr_pass"
    return f"sl_pass[{cpu_id - 1}]"


def agent_fail_ref(cpu_id: int) -> str:
    if cpu_id == 0:
        return "mstr_fail"
    return f"sl_fail[{cpu_id - 1}]"


def agent_slot_count_ref(cpu_id: int) -> str:
    if cpu_id == 0:
        return "mstr_slot_count"
    return f"sl_slot_count[{cpu_id - 1}]"


def manifest_agents(slaves: list[dict], master: dict | None) -> list[dict]:
    out: list[dict] = []
    if master and master.get("enabled") and master.get("targets"):
        out.append(master)
    out.extend(s for s in slaves if s.get("enabled") and s.get("targets"))
    return out


def parse_manifest(path: str) -> tuple[list[dict], dict | None]:
    with open(path, encoding="utf-8") as f:
        body = f.read()

    slaves = []
    for m in re.finditer(
        r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*POOL_WORD_\w+\s*,\s*(\d+)\s*,\s*(\d+)'
        r'(?:\s*,\s*"([^"]*)"\s*,\s*"([^"]*)")?\s*\}',
        body,
    ):
        slaves.append({
            "name": m.group(1),
            "cpu_id": int(m.group(2)),
            "tap": int(m.group(3)),
            "target_count": int(m.group(4)),
            "enabled": int(m.group(5)),
            "bus_type": m.group(6) or "task",
            "bus_port": m.group(7) or "",
        })

    master = None
    m_present = re.search(r"#define\s+CAMPAIGN_MASTER_PRESENT\s+(\d+)", body)
    if m_present and int(m_present.group(1)):
        mm = re.search(
            r'static const manifest_master_t MANIFEST_MASTER = \{\s*'
            r'"([^"]+)"\s*,\s*0\s*,\s*(\d+)\s*,',
            body,
        )
        if mm:
            master = {
                "name": mm.group(1),
                "cpu_id": 0,
                "tap": int(mm.group(2)),
                "enabled": 1,
            }

    target_blocks = re.findall(
        r"static const manifest_target_t (MANIFEST_\w+_TARGETS)\[\] = \{(.*?)\};",
        body,
        re.S,
    )
    targets_by_key = {}
    for key, block in target_blocks:
        entries = []
        for row in re.finditer(
            r"\{\s*([A-Z0-9_]+)\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*\"([^\"]+)\"\s*\}",
            block,
        ):
            entries.append({
                "sym": row.group(1),
                "addr": resolve_addr(row.group(1)),
                "expect": int(row.group(2), 0),
                "icode": row.group(3),
            })
        targets_by_key[key] = entries

    for s in slaves:
        key = f"MANIFEST_{s['name']}_TARGETS"
        s["targets"] = targets_by_key.get(key, [])
    if master:
        key = f"MANIFEST_{master['name']}_TARGETS"
        master["targets"] = targets_by_key.get(key, [])
    slaves.sort(key=lambda s: s["cpu_id"])
    return slaves, master


def load_icode_map(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {e["name"]: e for e in data["entries"]}


def load_pool_bytes(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        return int(json.load(f)["pool_bytes"])


def _padded_name(name: str, width: int = 8) -> str:
    return name.ljust(width)


def normalize_bus_type(name: str) -> str:
    n = name.strip().lower()
    aliases = {"apb": "apb3", "ahb": "ahb_lite", "axi": "axi4lite"}
    return aliases.get(n, n)


def cell_module_for(bus_type: str) -> str:
    return f"verif_vcpu_soc_cell_{normalize_bus_type(bus_type)}"


def load_soc_hierarchy_yaml(path: str) -> list[dict]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML required: pip install pyyaml") from exc
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    out = []
    for ent in raw.get("slaves") or []:
        full, dpi, _warn = parse_slave_yaml_ent(ent, label=f"hierarchy slave {ent.get('name')}")
        name, cpu_id = require_slave_name_cpu_id(full, dpi)
        bt = normalize_bus_type(str(dpi.get("bus_type", "axi4lite")))
        ab = dpi.get("addr_base", full.get("addr_base", 0))
        az = dpi.get("addr_size", full.get("addr_size", 0x1000))
        out.append({
            "name": name,
            "cpu_id": cpu_id,
            "tap_port": int(dpi.get("tap_port", cpu_id)),
            "bus_type": bt,
            "bus_port": str(dpi.get("bus_port", "") or ""),
            "addr_base": int(ab, 0) if isinstance(ab, str) else int(ab),
            "addr_size": int(az, 0) if isinstance(az, str) else int(az),
        })
    out.sort(key=lambda s: s["cpu_id"])
    return out


def soc_manifest_slaves(
    cpus: list[dict],
    hierarchy: list[dict],
    manifest_slaves: list[dict] | None = None,
) -> list[dict]:
    """Merge campaign actives with soc_hierarchy bus_type/bus_port + manifest targets."""
    active_ids = {c["id"] for c in cpus if c.get("enabled", 1)}
    by_id = {h["cpu_id"]: h for h in hierarchy}
    mby_id = {
        s["cpu_id"]: s for s in (manifest_slaves or []) if s.get("enabled")
    }
    merged = []
    for c in cpus:
        if not c.get("enabled", 1):
            continue
        hid = c["id"]
        h = by_id.get(hid, {})
        ms = mby_id.get(hid, {})
        merged.append({
            "name": c["name"],
            "cpu_id": hid,
            "tap_port": h.get("tap_port", ms.get("tap", hid - 1)),
            "bus_type": h.get("bus_type", "axi4lite"),
            "bus_port": h.get("bus_port", ""),
            "addr_base": h.get("addr_base"),
            "addr_size": h.get("addr_size", 0x1000),
            "pool_word": c["pool_word"],
            "role": c.get("role", "generic"),
            "targets": ms.get("targets", []),
            "enabled": ms.get("enabled", 1),
        })
    if not merged and hierarchy:
        for h in hierarchy:
            if h["cpu_id"] in active_ids or not active_ids:
                ms = mby_id.get(h["cpu_id"], {})
                merged.append({
                    **h,
                    "pool_word": (h["cpu_id"] - 1) * 0x800,
                    "role": "generic",
                    "targets": ms.get("targets", []),
                    "enabled": ms.get("enabled", 1),
                })
    return merged


def _active_manifest_slaves(slaves: list[dict]) -> list[dict]:
    return [s for s in slaves if s.get("enabled") and s.get("targets")]


def manifest_wired_slaves(manifest_slaves: list[dict]) -> list[dict]:
    """Manifest rows with external bus_port (active + reserved BUS_LAYOUT slots)."""
    out = []
    for s in manifest_slaves:
        bt = normalize_bus_type(str(s.get("bus_type") or "task"))
        port = str(s.get("bus_port") or "").strip()
        if bt in ("task", "none") or not port:
            continue
        row = {**s, "bus_type": bt}
        out.append(row)
    out.sort(key=lambda s: s["cpu_id"])
    return out


def _decode_regions(slaves: list[dict], hierarchy: list[dict]) -> list[tuple[int, int, int, int]]:
    """(addr_lo, addr_hi, gi, tap_port) sorted by addr_lo."""
    by_id = {s["cpu_id"]: s for s in slaves}
    regions: list[tuple[int, int, int, int]] = []
    for h in hierarchy:
        cid = h["cpu_id"]
        if cid not in by_id:
            continue
        gi = cid - 1
        tap = int(h.get("tap_port", gi))
        base = h.get("addr_base")
        size = h.get("addr_size", 0x1000)
        if base is None:
            tgts = by_id[cid].get("targets") or []
            if not tgts:
                continue
            addrs = [t["addr"] for t in tgts]
            base = min(addrs) & ~0xFFF
            size = max(addrs) - base + 0x1000
        lo = int(base)
        hi = lo + int(size)
        regions.append((lo, hi, gi, tap))
    regions.sort(key=lambda r: r[0])
    return regions


def _emit_decode_if_chain(
    regions: list[tuple[int, int, int, int]],
    bridge_call: str,
) -> list[str]:
    """if / else if chain for address regions (no trailing else — defaults set by caller)."""
    lines: list[str] = []
    for i, (lo, hi, gi, tap) in enumerate(regions):
        kw = "if" if i == 0 else "else if"
        lines.extend([
            f"      {kw} (addr >= 32'h{lo:08X} && addr < 32'h{hi:08X}) begin",
            f"        port = 2'd{tap};",
            f"        g_slv{gi}.u_bus.u_bridge.{bridge_call}",
            "      end",
        ])
    if not regions:
        lines.append("      ;")
    return lines


def generate_manifest_decode_vh(slaves: list[dict], hierarchy: list[dict]) -> str:
    regions = _decode_regions(slaves, hierarchy)
    lines = [
        "// Auto-generated by gen_tb_campaign.py — manifest address decode (real bridges)",
        "// Included inside module tb_soc_manifest",
        "",
        "  task manifest_decode_read;",
        "    input  [31:0] addr;",
        "    input  [2:0]  size;",
        "    output [31:0] data;",
        "    output [1:0]  resp;",
        "    output [1:0]  port;",
        "    begin",
        "      port = 2'd3;",
        "      data = 32'hDEAD_DEAD;",
        "      resp = 2'd2;",
    ]
    lines.extend(_emit_decode_if_chain(regions, "bus_read(addr, size, data, resp);"))
    lines.extend([
        "    end",
        "  endtask",
        "",
        "  task manifest_decode_write;",
        "    input  [31:0] addr;",
        "    input  [31:0] data;",
        "    input  [2:0]  size;",
        "    output [1:0]  resp;",
        "    output [1:0]  port;",
        "    begin",
        "      port = 2'd3;",
        "      resp = 2'd2;",
    ])
    lines.extend(_emit_decode_if_chain(regions, "bus_write(addr, data, size, resp);"))
    lines.extend([
        "    end",
        "  endtask",
        "",
    ])
    return "\n".join(lines)


def merge_bind_slaves(soc_slaves: list[dict], wired: list[dict]) -> list[dict]:
    """Union soc-manifest cells with manifest wired rows (64-slot BUS_LAYOUT)."""
    by_id = {s["cpu_id"]: s for s in soc_slaves}
    for w in wired:
        by_id[w["cpu_id"]] = w
    return sorted(by_id.values(), key=lambda s: s["cpu_id"])


def generate_bus_bind_vh(
    slaves: list[dict],
    xmr_prefix: str,
    read_comment: str,
    write_comment: str,
) -> tuple[str, str]:
    read_lines = [f"// Auto-generated by gen_tb_campaign.py — {read_comment}", "        case (CPU_ID)"]
    write_lines = [f"// Auto-generated by gen_tb_campaign.py — {write_comment}", "        case (CPU_ID)"]
    for s in slaves:
        gi = s["cpu_id"] - 1
        cid = s["cpu_id"]
        path = f"{xmr_prefix}.g_slv{gi}.u_bus.u_bridge"
        read_lines.append(
            f"          7'd{cid}: {path}.bus_read(addr, size, data, resp);"
        )
        write_lines.append(
            f"          7'd{cid}: {path}.bus_write(addr, data, size, resp);"
        )
    read_lines.extend([
        "          default: begin data = 32'h0; resp = 2'd2; end",
        "        endcase",
        "",
    ])
    write_lines.extend([
        "          default: resp = 2'd2;",
        "        endcase",
        "",
    ])
    return "\n".join(read_lines), "\n".join(write_lines)


def generate_chip_decode_vh(hierarchy: list[dict]) -> str:
    slaves = [{**h, "targets": []} for h in hierarchy]
    regions = _decode_regions(slaves, hierarchy)
    lines = [
        "// Auto-generated by gen_tb_campaign.py — chip address decode (real bridges)",
        "// Included inside module chip_top_example",
        "",
        "  task chip_decode_read;",
        "    input  [31:0] addr;",
        "    input  [2:0]  size;",
        "    output [31:0] data;",
        "    output [1:0]  resp;",
        "    output [1:0]  port;",
        "    begin",
        "      port = 2'd3;",
        "      data = 32'hDEAD_DEAD;",
        "      resp = 2'd2;",
    ]
    lines.extend(_emit_decode_if_chain(regions, "bus_read(addr, size, data, resp);"))
    lines.extend([
        "    end",
        "  endtask",
        "",
        "  task chip_decode_write;",
        "    input  [31:0] addr;",
        "    input  [31:0] data;",
        "    input  [2:0]  size;",
        "    output [1:0]  resp;",
        "    output [1:0]  port;",
        "    begin",
        "      port = 2'd3;",
        "      resp = 2'd2;",
    ])
    lines.extend(_emit_decode_if_chain(regions, "bus_write(addr, data, size, resp);"))
    lines.extend([
        "    end",
        "  endtask",
        "",
    ])
    return "\n".join(lines)


def emit_chip_agents(hierarchy: list[dict]) -> list[str]:
    lines: list[str] = []
    for h in hierarchy:
        gi = h["cpu_id"] - 1
        tap = h.get("tap_port", gi)
        name = _padded_name(h["name"])
        lines.extend([
            f"  verif_agent_slave #(.CPU_ID({h['cpu_id']}), .CPU_NAME(\"{name}\"), .TAP_PORT({tap})) u_ag_{h['cpu_id']} (",
            "    .phase(orch_phase), .boot_fw_offset(orch_boot_fw), .reset_pulse(orch_reset),",
            f"    .txn_valid(g_slv_snoop_v[{gi}]),",
            f"    .txn_is_write(g_slv_snoop_wr[{gi}]),",
            f"    .txn_addr(g_slv_snoop_addr[{gi}]),",
            f"    .txn_data(g_slv_snoop_data[{gi}]),",
            "    .icode_ptr(32'h0), .icode_kind(3'd0),",
            f"    .slot_count(sl_slot_count[{gi}]), .verify_pass(sl_pass[{gi}]),",
            f"    .verify_fail(sl_fail[{gi}]), .txn_recorded(sl_txns[{gi}])",
            "  );",
            "",
        ])
    return lines


def emit_chip_top_cells(hierarchy: list[dict]) -> list[str]:
    lines = ["  generate"]
    for h in hierarchy:
        gi = h["cpu_id"] - 1
        mod = cell_module_for(h["bus_type"])
        lines.append(f"    begin : g_slv{gi}")
        lines.extend(_emit_cell_instance(h, gi, indent="      "))
        lines.append("    end")
        lines.append("")
    lines.extend(["  endgenerate", ""])
    return lines


def emit_chip_apply_connects(hierarchy: list[dict]) -> list[str]:
    lines = ["  // Auto-generated CONNECT_SLV* from soc_hierarchy", ""]
    for h in hierarchy:
        cid = h["cpu_id"]
        bt = normalize_bus_type(h["bus_type"]).upper()
        macro = f"CONNECT_SLV{cid:02d}_{bt}"
        lines.extend([f"  `ifdef {macro}", f"    `{macro};", "  `endif", ""])
    return lines


def chip_hierarchy_bus_keys(hierarchy: list[dict]) -> set[str]:
    return {normalize_bus_type(str(h.get("bus_type") or "task")) for h in hierarchy}


def emit_chip_top_rtl_mk(hierarchy: list[dict]) -> str:
    """Tier-scoped iverilog file list for chip_top_example (no full BUS_RTL/STUB dump)."""
    keys = chip_hierarchy_bus_keys(hierarchy)
    bus_mods: set[str] = set()
    stub_mods: set[str] = set()
    for key in sorted(keys):
        spec = BUS_TYPES.get(key)
        if not spec or not spec.rtl_module:
            continue
        if key in CHIP_STUB_BUS_KEYS:
            stub_mods.add(spec.rtl_module)
        else:
            bus_mods.add(spec.rtl_module)
        for dep in CHIP_MASTER_DEPS.get(key, []):
            bus_mods.add(dep)
        slave = CHIP_SLAVE_RTL.get(key)
        if slave:
            bus_mods.add(slave)
    bus_rtl = " ".join(f"rtl/{m}.v" for m in sorted(bus_mods))
    stub_rtl = " ".join(f"rtl/{m}.v" for m in sorted(stub_mods))
    return "\n".join([
        "# Auto-generated by gen_tb_campaign.py — chip_top tier-scoped RTL",
        f"# hierarchy: {len(hierarchy)} slave(s), bus keys: {', '.join(sorted(keys))}",
        f"CHIP_BUS_RTL := {bus_rtl}" if bus_rtl else "CHIP_BUS_RTL :=",
        f"CHIP_STUB_RTL := {stub_rtl}" if stub_rtl else "CHIP_STUB_RTL :=",
        "",
    ])


def write_chip_soc_cell(hierarchy: list[dict]) -> None:
    keys = sorted(chip_hierarchy_bus_keys(hierarchy))
    script = os.path.join(ROOT, "gen_soc_cell_rtl.py")
    cmd = [sys.executable, script, "--only", ",".join(keys), "--out", OUT_CHIP_SOC_CELL, "--no-widths"]
    subprocess.run(cmd, check=True, cwd=ROOT)


def generate_chip_top_gen_vh(hierarchy: list[dict]) -> str:
    max_gi = max((h["cpu_id"] for h in hierarchy), default=1)
    wired = _slaves_with_bus_port(hierarchy)
    out = [
        "// Auto-generated by gen_tb_campaign.py — chip_top_example fabric + cells",
        "// Included inside module chip_top_example",
        "// Edit soc_hierarchy*.yaml then: make icodes (or make bus_connect_yaml)",
        "",
    ]
    out.extend(emit_chip_top_snoop_wires(max_gi))
    if _wired_needs_bus_widths(wired):
        out.extend(emit_bus_soc_width_localparams(wired))
    out.extend(emit_scale_soc_port_wires(wired))
    out.extend(emit_soc_axi_id_assigns(wired))
    out.extend(emit_soc_stub_periph(wired))
    out.extend(emit_chip_top_cells(hierarchy))
    out.extend(emit_chip_agents(hierarchy))
    out.extend(emit_chip_apply_connects(hierarchy))
    out.extend(emit_chip_top_bus_test_macro(hierarchy))
    out.extend(emit_chip_top_run_phase_a_macro(hierarchy))
    out.extend(emit_chip_top_agent_checks_macro(hierarchy))
    return "\n".join(out)


ADDR_V_RANGE = "[VERIF_ADDR_WIDTH-1:0]"
DATA_V_RANGE = "[VERIF_DATA_WIDTH-1:0]"
STRB_V_RANGE = "[VERIF_STRB_WIDTH-1:0]"
AXI_ID_V_RANGE = "[VERIF_AXI_ID_WIDTH-1:0]"
AXI_ID_V_ZERO = "{VERIF_AXI_ID_WIDTH{1'b0}}"


def _wired_needs_bus_widths(wired: list[dict]) -> bool:
    return len(wired) > 0


def emit_bus_soc_width_localparams(wired: list[dict]) -> list[str]:
    lines = [
        f"  localparam integer VERIF_ADDR_WIDTH = {ADDR_WIDTH_DEFAULT};",
        f"  localparam integer VERIF_DATA_WIDTH = {DATA_WIDTH_DEFAULT};",
        "  localparam integer VERIF_STRB_WIDTH = VERIF_DATA_WIDTH / 8;",
    ]
    if any(normalize_bus_type(s["bus_type"]).startswith("axi") for s in wired):
        lines.append(f"  localparam integer VERIF_AXI_ID_WIDTH = {AXI_ID_WIDTH_DEFAULT};")
        lines.append(
            f"  localparam integer VERIF_AXI_MAX_OUTSTANDING = {AXI_MAX_OUTSTANDING_DEFAULT};"
        )
    if any(normalize_bus_type(s["bus_type"]) == "ahb" for s in wired):
        from amba_bus_registry import AHB_MAX_OUTSTANDING_DEFAULT  # noqa: WPS433

        lines.append(
            f"  localparam integer VERIF_AHB_MAX_OUTSTANDING = {AHB_MAX_OUTSTANDING_DEFAULT};"
        )
    lines.extend([
        "  // SSOT: firmware/campaign/amba_bus_registry.py — regen: make -C firmware/campaign icodes",
        "",
    ])
    return lines


def _emit_cell_instance(s: dict, gi: int, indent: str = "      ") -> list[str]:
    mod = cell_module_for(s["bus_type"])
    bt = s["bus_type"]
    width_params = (
        f".CPU_ID({s['cpu_id']}), .ADDR_WIDTH(VERIF_ADDR_WIDTH), .DATA_WIDTH(VERIF_DATA_WIDTH)"
    )
    lines = [f"{indent}{mod} #({width_params}) u_bus ("]
    if bt.startswith("apb"):
        lines.append(f"{indent}.PCLK(soc_clk), .PRESETn(soc_rstn),")
        if bt == "apb2":
            lines.append(f"{indent}.PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(),")
            lines.append(f"{indent}.PRDATA(),")
        elif bt == "apb3":
            lines.append(
                f"{indent}.PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(),"
                f" .PRDATA(), .PREADY(), .PSLVERR(),"
            )
        else:
            extra = " .PPROT()," if bt in ("apb4", "apb5") else ""
            wake = " .PWAKEUP()," if bt == "apb5" else ""
            lines.append(
                f"{indent}.PADDR(), .PSEL(), .PENABLE(), .PWRITE(), .PWDATA(), .PSTRB(),"
                f"{extra}{wake} .PRDATA(), .PREADY(), .PSLVERR(),"
            )
    elif bt.startswith("ahb"):
        lines.append(f"{indent}.HCLK(soc_clk), .HRESETn(soc_rstn),")
        if bt in ("ahb5_lite", "ahb"):
            lines.append(f"{indent}.HEXOK(1'b1),")
        if bt == "ahb_lite":
            lines.append(
                f"{indent}.HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),"
                f" .HRDATA(), .HREADY(), .HRESP(),"
            )
        elif bt == "ahb5_lite":
            lines.append(
                f"{indent}.HADDR(), .HSIZE(), .HTRANS(), .HWRITE(), .HWDATA(),"
                f" .HNONSEC(), .HEXCL(), .HRDATA(), .HREADY(), .HRESP(), .HEXOK(),"
            )
        else:
            lines.append(
                f"{indent}.HADDR(), .HSIZE(), .HTRANS(), .HBURST(), .HPROT(), .HMASTLOCK(),"
                f" .HWRITE(), .HWDATA(), .HNONSEC(), .HEXCL(),"
                f" .HRDATA(), .HREADY(), .HRESP(), .HEXOK(),"
            )
    else:
        axi_prot = {"axi3full": 3, "axi4full": 4, "axi5full": 5}.get(bt)
        if axi_prot:
            lines[0] = (
                f"{indent}{mod} #(.CPU_ID({s['cpu_id']}), .ADDR_WIDTH(VERIF_ADDR_WIDTH),"
                f" .DATA_WIDTH(VERIF_DATA_WIDTH), .AXI_PROT({axi_prot}),"
                f" .ID_WIDTH(VERIF_AXI_ID_WIDTH),"
                f" .MAX_OUTSTANDING(VERIF_AXI_MAX_OUTSTANDING)) u_bus ("
            )
        elif bt == "ahb":
            lines[0] = (
                f"{indent}{mod} #(.CPU_ID({s['cpu_id']}), .ADDR_WIDTH(VERIF_ADDR_WIDTH),"
                f" .DATA_WIDTH(VERIF_DATA_WIDTH),"
                f" .MAX_OUTSTANDING(VERIF_AHB_MAX_OUTSTANDING)) u_bus ("
            )
        elif bt == "ace":
            lines[0] = (
                f"{indent}{mod} #(.CPU_ID({s['cpu_id']}), .ADDR_WIDTH(VERIF_ADDR_WIDTH),"
                f" .DATA_WIDTH(VERIF_DATA_WIDTH), .AXI_PROT(4),"
                f" .ID_WIDTH(VERIF_AXI_ID_WIDTH),"
                f" .MAX_OUTSTANDING(VERIF_AXI_MAX_OUTSTANDING)) u_bus ("
            )
        lines.append(f"{indent}.ACLK(soc_clk), .ARESETn(soc_rstn),")
        if bt == "axi4lite":
            lines.append(
                f"{indent}.ARVALID(), .ARADDR(), .ARSIZE(), .RREADY(),"
                f" .AWVALID(), .AWADDR(), .AWSIZE(), .WVALID(), .WDATA(), .WSTRB(), .BREADY(),"
                f" .ARREADY(), .RVALID(), .RDATA(), .RRESP(),"
                f" .AWREADY(), .WREADY(), .BVALID(), .BRESP(),"
            )
        else:
            qos = " .ARQOS(), .ARREGION()," if bt in ("axi4full", "axi5full") else ""
            awqos = " .AWQOS(), .AWREGION(), .AWATOP()," if bt in ("axi4full", "axi5full") else ""
            lines.append(
                f"{indent}.ARID(), .ARADDR(), .ARLEN(), .ARSIZE(), .ARBURST(), .ARVALID(), .RREADY(),"
                f"{qos}"
                f" .AWID(), .AWADDR(), .AWLEN(), .AWSIZE(), .AWBURST(), .AWVALID(),"
                f"{awqos}"
                f" .WID(), .WDATA(), .WSTRB(), .WLAST(), .WVALID(), .BREADY(),"
                f" .ARREADY(), .RID(), .RVALID(), .RDATA(), .RRESP(), .RLAST(),"
                f" .AWREADY(), .WREADY(), .BID(), .BVALID(), .BRESP(),"
            )
    lines.extend([
        f"{indent}.snoop_valid(g_slv_snoop_v[{gi}]), .snoop_wr(g_slv_snoop_wr[{gi}]),",
        f"{indent}.snoop_addr(g_slv_snoop_addr[{gi}]), .snoop_data(g_slv_snoop_data[{gi}])",
        f"{indent});",
    ])
    return lines


def emit_soc_manifest_apply_connects(wired: list[dict]) -> list[str]:
    lines = ["  // Auto-generated CONNECT_SLV* (manifest / BUS_LAYOUT)", ""]
    for s in wired:
        cid = s["cpu_id"]
        tag = connect_slv_tag(s["bus_type"])
        if not tag:
            continue
        macro = f"CONNECT_SLV{cid:02d}_{tag}"
        lines.extend([f"  `ifdef {macro}", f"    `{macro};", "  `endif", ""])
    return lines


def generate_soc_manifest_scale_defs_vh(wired: list[dict]) -> str:
    n = len(wired)
    max_gi = max((s["cpu_id"] for s in wired), default=0)
    last_gi = max_gi - 1 if max_gi else 0
    last_ok = (
        f"(g_slv{last_gi}.u_bus.u_cpu.CPU_ID == {max_gi})"
        if max_gi else "1'b0"
    )
    lines = [
        "// Auto-generated by gen_tb_campaign.py — 60-slot scale integration TB",
        "`ifndef TB_SOC_MANIFEST_SCALE_DEFS_VH",
        "`define TB_SOC_MANIFEST_SCALE_DEFS_VH",
        "",
        f"`define SOC_MANIFEST_SCALE_NUM_WIRED {n}",
        f"`define SOC_MANIFEST_SCALE_MAX_GI {max_gi}",
        f"`define SOC_MANIFEST_SCALE_LAST_GI {last_gi}",
        f"`define SOC_MANIFEST_SCALE_LAST_CELL_OK {last_ok}",
        "",
        "`endif",
        "",
    ]
    return "\n".join(lines)


_STUB_INIT_BY_NAME: dict[str, tuple[int | None, int | None]] = {
    "SRAM": (0xDEADBEEF, 0xCAFEBABE),
    "UART": (0x00000080, 0xDEADDEAD),
}

_CHIP_BUS_TEST_PATTERNS = [0x0000CAFE, 0x12345678, 0x000000A5, 0xDEADBEEF]


def _stub_init_for_slave(s: dict) -> tuple[int | None, int | None]:
    return _STUB_INIT_BY_NAME.get(str(s.get("name", "")), (None, None))


def _slaves_with_bus_port(slaves: list[dict]) -> list[dict]:
    return [s for s in slaves if str(s.get("bus_port") or "").strip()]


def emit_soc_manifest_snoop_wires(n: int) -> list[str]:
    if n <= 0:
        n = 1
    return [
        f"  wire [{n}-1:0]        g_slv_snoop_v;",
        f"  wire [{n}-1:0]        g_slv_snoop_wr;",
        f"  wire [31:0] g_slv_snoop_addr [0:{n}-1];",
        f"  wire [31:0] g_slv_snoop_data [0:{n}-1];",
        "",
        f"  wire [31:0] sl_slot_count [0:{n}-1];",
        f"  wire [31:0] sl_pass       [0:{n}-1];",
        f"  wire [31:0] sl_fail       [0:{n}-1];",
        f"  wire [31:0] sl_txns       [0:{n}-1];",
        "",
    ]


def emit_soc_axi_id_assigns(slaves: list[dict]) -> list[str]:
    """AXI full-port ID tie-offs for stub slaves (open interconnect wires)."""
    lines: list[str] = []
    seen: set[str] = set()
    for s in slaves:
        pref = str(s.get("bus_port") or "").strip()
        if not pref or pref in seen:
            continue
        bt = normalize_bus_type(s["bus_type"])
        if not bt.startswith("axi") or bt == "axi4lite":
            continue
        seen.add(pref)
        lines.extend([
            f"  assign {pref}_rid = {AXI_ID_V_ZERO};",
            f"  assign {pref}_bid = {AXI_ID_V_ZERO};",
            f"  assign {pref}_rlast = 1'b1;",
            "",
        ])
    return lines


def emit_soc_stub_periph(slaves: list[dict]) -> list[str]:
    """Manifest-driven stub SoC peripherals (addr_base + bus_port from yaml/manifest)."""
    lines = ["  // Auto-generated stub peripherals — edit soc_hierarchy YAML, not this file", ""]
    for s in slaves:
        pref = str(s.get("bus_port") or "").strip()
        if not pref:
            continue
        base = int(s.get("addr_base") or 0)
        bt = normalize_bus_type(s["bus_type"])
        name = str(s.get("name") or f"CPU{s['cpu_id']}")
        inst = f"u_stub_{re.sub(r'[^A-Za-z0-9_]', '_', name.lower())}"
        w0, w1 = _stub_init_for_slave(s)
        if bt.startswith("apb"):
            mod_slave = "verif_apb2_slave_simple" if bt == "apb2" else "verif_apb_slave_simple"
            lines.append(
                f"  {mod_slave} #(.ADDR_WIDTH(VERIF_ADDR_WIDTH), .DATA_WIDTH(VERIF_DATA_WIDTH),"
                f" .BASE(32'h{base:08X})) {inst} ("
            )
            lines.append("    .PCLK(soc_clk), .PRESETn(soc_rstn),")
            lines.append(
                f"    .PADDR({pref}_PADDR), .PSEL({pref}_PSEL), .PENABLE({pref}_PENABLE),"
                f" .PWRITE({pref}_PWRITE), .PWDATA({pref}_PWDATA),"
            )
            if bt == "apb2":
                lines.append(f"    .PRDATA({pref}_PRDATA)")
            else:
                lines.append(
                    f"    .PSTRB({pref}_PSTRB), .PRDATA({pref}_PRDATA),"
                    f" .PREADY({pref}_PREADY), .PSLVERR({pref}_PSLVERR)"
                )
            lines.extend(["  );", ""])
        elif bt.startswith("ahb"):
            params = [
                ".ADDR_WIDTH(VERIF_ADDR_WIDTH)",
                ".DATA_WIDTH(VERIF_DATA_WIDTH)",
                f".BASE(32'h{base:08X})",
            ]
            if w0 is not None:
                params.append(f".INIT_WORD0(32'h{w0:08X})")
            if w1 is not None:
                params.append(f".INIT_WORD1(32'h{w1:08X})")
            lines.append(f"  verif_ahb_lite_slave_simple #({', '.join(params)}) {inst} (")
            lines.extend([
                "    .HCLK(soc_clk), .HRESETn(soc_rstn),",
                f"    .HADDR({pref}_HADDR), .HSIZE({pref}_HSIZE), .HTRANS({pref}_HTRANS),",
                f"    .HWRITE({pref}_HWRITE), .HWDATA({pref}_HWDATA), .HREADY({pref}_HREADY),",
                f"    .HRDATA({pref}_HRDATA), .HREADYOUT({pref}_HREADYOUT), .HRESP({pref}_HRESP)",
                "  );",
                "",
            ])
        else:
            params = [f".BASE(32'h{base:08X})"]
            if w0 is not None:
                params.append(f".INIT_WORD0(32'h{w0:08X})")
            if w1 is not None:
                params.append(f".INIT_WORD1(32'h{w1:08X})")
            rid_w = f"{inst}_rid"
            bid_w = f"{inst}_bid"
            rlast_w = f"{inst}_rlast"
            lines.extend([
                f"  wire {AXI_ID_V_RANGE} {rid_w}, {bid_w};",
                f"  wire       {rlast_w};",
            ])
            params[:0] = [
                ".ADDR_WIDTH(VERIF_ADDR_WIDTH)",
                ".DATA_WIDTH(VERIF_DATA_WIDTH)",
                ".ID_WIDTH(VERIF_AXI_ID_WIDTH)",
            ]
            lines.append(f"  verif_axi_full_slave_simple #({', '.join(params)}) {inst} (")
            if bt == "axi4lite":
                lines.extend([
                    "    .ACLK(soc_clk), .ARESETn(soc_rstn),",
                    f"    .ARID({AXI_ID_V_ZERO}), .ARADDR({pref}_araddr), .ARLEN(8'd0), .ARSIZE({pref}_arsize),",
                    f"    .ARBURST(2'b01), .ARVALID({pref}_arvalid), .ARREADY({pref}_arready),",
                    f"    .RID({rid_w}), .RDATA({pref}_rdata), .RRESP({pref}_rresp),",
                    f"    .RLAST({pref}_rvalid), .RVALID({pref}_rvalid), .RREADY({pref}_rready),",
                    f"    .AWID({AXI_ID_V_ZERO}), .AWADDR({pref}_awaddr), .AWLEN(8'd0), .AWSIZE({pref}_awsize),",
                    f"    .AWBURST(2'b01), .AWVALID({pref}_awvalid), .AWREADY({pref}_awready),",
                    f"    .WID({AXI_ID_V_ZERO}), .WDATA({pref}_wdata), .WSTRB({pref}_wstrb), .WLAST(1'b1),",
                    f"    .WVALID({pref}_wvalid), .WREADY({pref}_wready),",
                    f"    .BID({bid_w}), .BRESP({pref}_bresp), .BVALID({pref}_bvalid), .BREADY({pref}_bready)",
                    "  );",
                    "",
                ])
            else:
                lines.extend([
                    "    .ACLK(soc_clk), .ARESETn(soc_rstn),",
                    f"    .ARID({AXI_ID_V_ZERO}), .ARADDR({pref}_araddr), .ARLEN(8'd0), .ARSIZE({pref}_arsize),",
                    f"    .ARBURST(2'b01), .ARVALID({pref}_arvalid), .ARREADY({pref}_arready),",
                    f"    .RID({rid_w}), .RDATA({pref}_rdata), .RRESP({pref}_rresp),",
                    f"    .RLAST({rlast_w}), .RVALID({pref}_rvalid), .RREADY({pref}_rready),",
                    f"    .AWID({AXI_ID_V_ZERO}), .AWADDR({pref}_awaddr), .AWLEN(8'd0), .AWSIZE({pref}_awsize),",
                    f"    .AWBURST(2'b01), .AWVALID({pref}_awvalid), .AWREADY({pref}_awready),",
                    f"    .WID({AXI_ID_V_ZERO}), .WDATA({pref}_wdata), .WSTRB({pref}_wstrb), .WLAST(1'b1),",
                    f"    .WVALID({pref}_wvalid), .WREADY({pref}_wready),",
                    f"    .BID({bid_w}), .BRESP({pref}_bresp), .BVALID({pref}_bvalid), .BREADY({pref}_bready)",
                    "  );",
                    f"  assign {pref}_rid = {rid_w};",
                    f"  assign {pref}_bid = {bid_w};",
                    f"  assign {pref}_rlast = {rlast_w};",
                    "",
                ])
    return lines


def emit_soc_manifest_phase_a_checks(slaves: list[dict]) -> list[str]:
    lines = ["`define SOC_MANIFEST_PHASE_A_CHECKS \\"]
    for s in slaves:
        gi = s["cpu_id"] - 1
        name = s["name"]
        lines.extend([
            f'  check("{name} Phase A stopped", g_slv{gi}.u_bus.u_cpu.sim_stop); \\',
            f'  check("{name} bus_txn_count > 0", g_slv{gi}.u_bus.u_cpu.bus_txn_count > 0); \\',
            f'  check("Agent {name} saw traffic", sl_txns[{gi}] > 0); \\',
        ])
    lines.append("")
    return lines


def emit_chip_top_snoop_wires(max_gi: int) -> list[str]:
    if max_gi <= 0:
        max_gi = 1
    return [
        f"  localparam HIER_N = {max_gi};",
        "",
        f"  wire [HIER_N-1:0]        g_slv_snoop_v;",
        f"  wire [HIER_N-1:0]        g_slv_snoop_wr;",
        f"  wire [31:0] g_slv_snoop_addr [0:HIER_N-1];",
        f"  wire [31:0] g_slv_snoop_data [0:HIER_N-1];",
        "",
        f"  wire [31:0] sl_slot_count [0:HIER_N-1];",
        f"  wire [31:0] sl_pass       [0:HIER_N-1];",
        f"  wire [31:0] sl_fail       [0:HIER_N-1];",
        f"  wire [31:0] sl_txns       [0:HIER_N-1];",
        "",
    ]


def emit_chip_top_bus_test_macro(hierarchy: list[dict]) -> list[str]:
    lines = ["`define SOC_CHIP_TOP_BUS_TESTS \\"]
    for i, h in enumerate(hierarchy):
        pat = _CHIP_BUS_TEST_PATTERNS[i % len(_CHIP_BUS_TEST_PATTERNS)]
        bt = normalize_bus_type(h["bus_type"]).upper()
        base = int(h.get("addr_base") or 0)
        lines.append(
            f'  chip_bus_wr_rd("{h["name"]} {bt}", 32\'h{base:08X}, 32\'h{pat:08X}); \\'
        )
    lines.append("")
    return lines


def emit_chip_top_agent_checks_macro(hierarchy: list[dict]) -> list[str]:
    lines = ["`define SOC_CHIP_TOP_AGENT_CHECKS \\"]
    for h in hierarchy:
        gi = h["cpu_id"] - 1
        lines.append(
            f'  check("Agent {h["name"]} saw bridge traffic", sl_txns[{gi}] > 0); \\'
        )
    lines.append("")
    return lines


def emit_chip_top_run_phase_a_macro(hierarchy: list[dict]) -> list[str]:
    lines = ["`define SOC_CHIP_TOP_RUN_PHASE_A \\"]
    for h in hierarchy:
        lines.append(f"  u_ag_{h['cpu_id']}.run_phase_a(); \\")
    lines.append("")
    return lines


def emit_scale_soc_port_wires(wired: list[dict]) -> list[str]:
    """Declare interconnect-side wires for CONNECT_SLV* macros (open stubs)."""
    lines = ["  // SoC port stubs for wired slaves (scale compile)", ""]
    seen: set[str] = set()
    for s in wired:
        pref = str(s.get("bus_port") or "").strip()
        if not pref or pref in seen:
            continue
        seen.add(pref)
        bt = normalize_bus_type(s["bus_type"])
        if bt.startswith("apb"):
            apb_wires = [
                f"  wire {ADDR_V_RANGE} {pref}_PADDR;",
                f"  wire {DATA_V_RANGE} {pref}_PWDATA, {pref}_PRDATA;",
                f"  wire        {pref}_PSEL, {pref}_PENABLE, {pref}_PWRITE;",
                f"  wire        {pref}_PREADY, {pref}_PSLVERR;",
            ]
            if bt != "apb2":
                apb_wires.insert(3, f"  wire {STRB_V_RANGE} {pref}_PSTRB;")
            lines.extend(apb_wires)
            if bt in ("apb4", "apb5"):
                lines.append(f"  wire [2:0]  {pref}_PPROT;")
            if bt == "apb5":
                lines.append(f"  wire        {pref}_PWAKEUP;")
        elif bt.startswith("ahb"):
            lines.extend([
                f"  wire {ADDR_V_RANGE} {pref}_HADDR;",
                f"  wire {DATA_V_RANGE} {pref}_HWDATA, {pref}_HRDATA;",
                f"  wire [2:0]  {pref}_HSIZE;",
                f"  wire [1:0]  {pref}_HTRANS, {pref}_HRESP;",
                f"  wire        {pref}_HWRITE, {pref}_HREADY, {pref}_HREADYOUT;",
            ])
            if bt in ("ahb5_lite", "ahb"):
                lines.extend([
                    f"  wire        {pref}_HNONSEC, {pref}_HEXCL, {pref}_HEXOK;",
                ])
            if bt == "ahb":
                lines.extend([
                    f"  wire [2:0]  {pref}_HBURST;",
                    f"  wire [3:0]  {pref}_HPROT;",
                    f"  wire        {pref}_HMASTLOCK;",
                ])
        else:
            lines.extend([
                f"  wire        {pref}_arvalid, {pref}_arready, {pref}_rvalid, {pref}_rready;",
                f"  wire        {pref}_awvalid, {pref}_awready, {pref}_wvalid, {pref}_wready;",
                f"  wire        {pref}_bvalid, {pref}_bready, {pref}_rlast;",
                f"  wire {ADDR_V_RANGE} {pref}_araddr, {pref}_awaddr;",
                f"  wire {DATA_V_RANGE} {pref}_wdata, {pref}_rdata;",
                f"  wire [2:0]  {pref}_arsize, {pref}_awsize;",
                f"  wire {STRB_V_RANGE} {pref}_wstrb;",
                f"  wire [1:0]  {pref}_rresp, {pref}_bresp;",
            ])
            if bt != "axi4lite":
                lines.extend([
                    f"  wire {AXI_ID_V_RANGE} {pref}_arid, {pref}_awid, {pref}_wid, {pref}_rid, {pref}_bid;",
                    f"  wire [7:0]  {pref}_arlen, {pref}_awlen;",
                    f"  wire [1:0]  {pref}_arburst, {pref}_awburst;",
                ])
            if bt in ("axi4full", "axi5full"):
                lines.extend([
                    f"  wire [3:0]  {pref}_arqos, {pref}_arregion;",
                    f"  wire [3:0]  {pref}_awqos, {pref}_awregion;",
                ])
            if bt == "axi5full":
                lines.append(f"  wire [5:0]  {pref}_awatop;")
        lines.append("")
    return lines


def generate_soc_manifest_scale_body_vh(wired: list[dict], active: list[dict]) -> str:
    max_gi = max((s["cpu_id"] for s in wired), default=1)
    out = [
        "// Auto-generated by gen_tb_campaign.py — flat g_slv[] for scale integration",
        "// Included inside module tb_soc_manifest_scale",
        "",
        f"  localparam SCALE_MAX_GI = {max_gi};",
        f"  wire [SCALE_MAX_GI-1:0]        g_slv_snoop_v;",
        f"  wire [SCALE_MAX_GI-1:0]        g_slv_snoop_wr;",
        f"  wire [31:0] g_slv_snoop_addr [0:SCALE_MAX_GI-1];",
        f"  wire [31:0] g_slv_snoop_data [0:SCALE_MAX_GI-1];",
        "",
        f"  wire [31:0] sl_slot_count [0:SCALE_MAX_GI-1];",
        f"  wire [31:0] sl_pass       [0:SCALE_MAX_GI-1];",
        f"  wire [31:0] sl_fail       [0:SCALE_MAX_GI-1];",
        f"  wire [31:0] sl_txns       [0:SCALE_MAX_GI-1];",
        "",
    ]
    if _wired_needs_bus_widths(wired):
        out.extend(emit_bus_soc_width_localparams(wired))
    out.extend(emit_scale_soc_port_wires(wired))
    out.extend(emit_soc_axi_id_assigns(wired))
    out.extend(emit_soc_stub_periph(wired))
    out.extend(emit_soc_manifest_slaves(wired))
    out.extend(emit_soc_manifest_step_always(active))
    out.extend(emit_soc_manifest_agents(active))
    out.extend(emit_soc_manifest_setup(active))
    out.extend(emit_soc_manifest_run_cpu_task(active))
    out.extend(emit_soc_manifest_apply_connects(wired))
    return "\n".join(out)


def emit_soc_manifest_slaves(slaves: list[dict]) -> list[str]:
    lines = ["  generate"]
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.append(f"    begin : g_slv{gi}")
        lines.extend(_emit_cell_instance(s, gi, indent="      "))
        lines.append("    end")
        lines.append("")
    lines.append("  endgenerate")
    lines.append("")
    return lines


def emit_soc_manifest_step_always(slaves: list[dict]) -> list[str]:
    lines = [
        "  always @(posedge soc_clk) begin",
        "    if (soc_rstn) begin",
    ]
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.extend([
            f"      if (!g_slv{gi}.u_bus.u_cpu.sim_stop &&",
            f"          (g_slv{gi}.u_bus.u_cpu.state == `CPU_STATE_RUNNING ||",
            f"           g_slv{gi}.u_bus.u_cpu.state == `CPU_STATE_DUMMY))",
            f"        g_slv{gi}.u_bus.u_cpu.cpu_step();",
        ])
    lines.extend([
        "    end",
        "  end",
        "",
    ])
    return lines


def emit_soc_manifest_agents(slaves: list[dict]) -> list[str]:
    lines = []
    for s in slaves:
        gi = s["cpu_id"] - 1
        tap = s["tap_port"]
        name = _padded_name(s["name"])
        icode_ptr = (
            f"`ICODE_{s['name']}_SLOT0_PTR"
            if s.get("targets")
            else "32'h0"
        )
        lines.extend([
            f"  verif_agent_slave #(.CPU_ID({s['cpu_id']}), .CPU_NAME(\"{name}\"), .TAP_PORT({tap})) u_ag_{s['cpu_id']} (",
            "    .phase(orch_phase), .boot_fw_offset(orch_boot_fw), .reset_pulse(orch_reset),",
            f"    .txn_valid(g_slv_snoop_v[{gi}]),",
            f"    .txn_is_write(g_slv_snoop_wr[{gi}]),",
            f"    .txn_addr(g_slv_snoop_addr[{gi}]),",
            f"    .txn_data(g_slv_snoop_data[{gi}]),",
            f"    .icode_ptr({icode_ptr}), .icode_kind(3'd0),",
            f"    .slot_count(sl_slot_count[{gi}]), .verify_pass(sl_pass[{gi}]),",
            f"    .verify_fail(sl_fail[{gi}]), .txn_recorded(sl_txns[{gi}])",
            "  );",
            "",
        ])
    return lines


def emit_soc_manifest_setup(slaves: list[dict]) -> list[str]:
    lines = [
        "  task soc_manifest_setup_cpu;",
        "    input [3:0] cid;",
        "    input [8*8:1] name;",
        "    input [31:0] pool_base;",
        "    begin",
        "      case (cid)",
    ]
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.extend([
            f"        4'd{s['cpu_id']}: begin",
            f"          g_slv{gi}.u_bus.u_cpu.cpu_init();",
            f"          g_slv{gi}.u_bus.u_cpu.cpu_set_name(name);",
            f"          g_slv{gi}.u_bus.u_cpu.cpu_attach_pool_region(pool_base, FW_SIZE);",
            f"          g_slv{gi}.u_bus.u_cpu.cpu_attach_recorder();",
            "        end",
        ])
    lines.extend([
        "        default: ;",
        "      endcase",
        "    end",
        "  endtask",
        "",
        "  task soc_manifest_run_phase_a;",
        "    input [3:0] cid;",
        "    begin",
        "      case (cid)",
    ])
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.extend([
            f"        4'd{s['cpu_id']}: begin",
            f"          g_slv{gi}.u_bus.u_cpu.pc = 32'h000;",
            f"          g_slv{gi}.u_bus.u_cpu.state = `CPU_STATE_RUNNING;",
            f"          g_slv{gi}.u_bus.u_cpu.request_sim_stop = 0;",
            f"          g_slv{gi}.u_bus.u_cpu.sim_stop = 0;",
            "        end",
        ])
    lines.extend([
        "        default: ;",
        "      endcase",
        "    end",
        "  endtask",
        "",
    ])
    return lines


def emit_soc_manifest_run_cpu_task(slaves: list[dict]) -> list[str]:
    lines = [
        "  task soc_manifest_run_cpu;",
        "    input [3:0]  cid;",
        "    input [31:0] offset;",
        "    input [31:0] max_steps;",
        "    reg [31:0] cyc;",
        "    begin",
        "      case (cid)",
    ]
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.extend([
            f"        4'd{s['cpu_id']}: begin",
            f"          g_slv{gi}.u_bus.u_cpu.pc = offset;",
            f"          g_slv{gi}.u_bus.u_cpu.state = `CPU_STATE_RUNNING;",
            f"          g_slv{gi}.u_bus.u_cpu.request_sim_stop = 0;",
            f"          g_slv{gi}.u_bus.u_cpu.sim_stop = 0;",
            f"          for (cyc = 0; cyc < max_steps; cyc = cyc + 1) begin",
            f"            @(posedge soc_clk);",
            f"            if (g_slv{gi}.u_bus.u_cpu.request_sim_stop || g_slv{gi}.u_bus.u_cpu.sim_stop)",
            f"              cyc = max_steps;",
            "          end",
            "        end",
        ])
    lines.extend([
        "        default: ;",
        "      endcase",
        "    end",
        "  endtask",
        "",
        "  task soc_manifest_wait_stopped;",
        "    input [31:0] max_cyc;",
        "    reg [31:0] cyc;",
        "    reg        all_done;",
        "    begin",
        "      cyc = 0;",
        "      while (cyc < max_cyc) begin",
        "        all_done = 1;",
    ])
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.append(
            f"        if (!g_slv{gi}.u_bus.u_cpu.sim_stop) all_done = 0;"
        )
    lines.extend([
        "        if (all_done) cyc = max_cyc;",
        "        else begin",
        "          @(posedge soc_clk);",
        "          cyc = cyc + 1;",
        "        end",
        "      end",
        "    end",
        "  endtask",
        "",
        "  task soc_manifest_exec_icode;",
        "    input [3:0]  cid;",
        "    input [31:0] icode_ptr;",
        "    output       ok;",
        "    reg [31:0] txn_before;",
        "    begin",
        "      ok = 0;",
        "      case (cid)",
    ])
    for s in slaves:
        gi = s["cpu_id"] - 1
        lines.extend([
            f"        4'd{s['cpu_id']}: begin",
            f"          txn_before = g_slv{gi}.u_bus.u_cpu.bus_txn_count;",
            f"          u_pool.pool_use_array(cid);",
            "          u_pool.pool_assign_region(cid, `SOC_MANIFEST_POOL_ICODE, ICODE_POOL_SZ);",
            f"          g_slv{gi}.u_bus.u_cpu.pc = icode_ptr;",
            f"          g_slv{gi}.u_bus.u_cpu.state = `CPU_STATE_RUNNING;",
            f"          g_slv{gi}.u_bus.u_cpu.request_sim_stop = 0;",
            f"          g_slv{gi}.u_bus.u_cpu.sim_stop = 0;",
            f"          soc_manifest_run_cpu(cid, icode_ptr, 256);",
            f"          if (!g_slv{gi}.u_bus.u_cpu.sim_stop && !g_slv{gi}.u_bus.u_cpu.request_sim_stop)",
            f"            g_slv{gi}.u_bus.u_cpu.request_sim_stop = 1;",
            f"          soc_manifest_wait_stopped(64);",
            f"          repeat (4) @(posedge soc_clk);",
            f"          ok = (g_slv{gi}.u_bus.u_cpu.request_sim_stop || g_slv{gi}.u_bus.u_cpu.sim_stop)",
            f"               && (g_slv{gi}.u_bus.u_cpu.bus_txn_count > txn_before);",
            f"          u_pool.pool_use_array(cid);",
            f"          u_pool.pool_assign_region(cid, 32'h{s['pool_word']:x}, FW_SIZE);",
            "        end",
        ])
    lines.extend([
        "        default: ;",
        "      endcase",
        "    end",
        "  endtask",
        "",
    ])
    return lines


def emit_soc_manifest_init_steps_macro() -> list[str]:
    if not os.path.isfile(SOC_INIT_SEQ_VH):
        return []
    steps: list[str] = []
    in_macro = False
    with open(SOC_INIT_SEQ_VH, encoding="utf-8") as f:
        for line in f:
            if "SOC_INIT_RUN_STEPS" in line:
                in_macro = True
                continue
            if not in_macro:
                continue
            stripped = line.strip()
            if stripped.startswith("`endif"):
                break
            if not stripped.endswith("\\"):
                continue
            step = stripped[:-1].strip()
            step = step.replace("decode_read", "manifest_decode_read")
            step = step.replace("decode_write", "manifest_decode_write")
            if step:
                steps.append(step)
    if not steps:
        return []
    out = ["`define SOC_MANIFEST_INIT_STEPS \\"]
    out.extend(f"  {step} \\" for step in steps)
    out.append("")
    return out


def emit_soc_manifest_phase_macros(slaves: list[dict], pool_bytes: int) -> list[str]:
    active = _active_manifest_slaves(slaves)
    max_icode_slots = max((len(s["targets"]) for s in active), default=0)
    total_pass = sum(len(s["targets"]) for s in active)
    lines = [
        "`define SOC_MANIFEST_OFF_A 32'h000",
        "`define SOC_MANIFEST_OFF_B 32'h100",
        f"`define SOC_MANIFEST_ICODE_POOL_BYTES {pool_bytes}",
        f"`define SOC_MANIFEST_MAX_ICODE_SLOTS {max_icode_slots}",
        f"`define SOC_MANIFEST_TOTAL_ICODE_PASS {total_pass}",
        "",
        "`define SOC_MANIFEST_LOAD_POOL \\",
        '  u_pool.pool_load_hex("firmware/full_campaign_unified.hex"); \\',
    ]
    for s in slaves:
        lines.append(
            f"  u_pool.pool_assign_region(4'd{s['cpu_id']}, "
            f"`SOC_MANIFEST_POOL_{s['name']}, FW_SIZE); \\"
        )
    lines.extend([
        "  u_pool.pool_assign_region(4'd4, `SOC_MANIFEST_POOL_ICODE, ICODE_POOL_SZ); \\",
        "",
        "`define SOC_MANIFEST_SETUP_CPUS \\",
    ])
    for s in slaves:
        lines.append(
            f'  soc_manifest_setup_cpu(4\'d{s["cpu_id"]}, "{_padded_name(s["name"])}", '
            f"`SOC_MANIFEST_POOL_{s['name']}); \\"
        )
    lines.append("")
    lines.extend(emit_soc_manifest_init_steps_macro())
    lines.extend([
        "`define SOC_MANIFEST_RUN_PHASE_A \\",
        "  manifest_soc_run_init(); \\",
    ])
    for s in slaves:
        lines.append(f"  u_ag_{s['cpu_id']}.run_phase_a(); \\")
    for s in slaves:
        lines.append(
            f"  soc_manifest_run_phase_a(4'd{s['cpu_id']}); \\"
        )
    lines.extend([
        "  soc_manifest_wait_stopped(MAX_WAIT); \\",
        "",
        "`define SOC_MANIFEST_BUS_READS \\",
    ])
    for s in active:
        for t in s["targets"]:
            lines.append(
                f"  manifest_decode_read(32'h{t['addr']:08X}, 3'd4, rdata, rresp, rport); \\"
            )
    lines.append("")
    lines.extend([
        "`define SOC_MANIFEST_RUN_PHASE_B \\",
        "  u_mstr.phase_release(`PHASE_COLLECT, `SOC_MANIFEST_OFF_B); \\",
        "  u_orch.phase_release(`PHASE_COLLECT, `SOC_MANIFEST_OFF_B); \\",
        "  u_mstr.inject_read_hints(); \\",
        "  `SOC_MANIFEST_BUS_READS \\",
    ])
    for s in slaves:
        lines.append(f"  u_ag_{s['cpu_id']}.run_phase_b(); \\")
    for s in slaves:
        lines.append(
            f"  soc_manifest_run_cpu(4'd{s['cpu_id']}, `SOC_MANIFEST_OFF_B, 48); \\"
        )
    lines.append("")
    slot_checks = " && ".join(
        f"sl_slot_count[{s['cpu_id'] - 1}] >= {len(s['targets'])}" for s in active
    ) or "1"
    lines.append(f"`define SOC_MANIFEST_PHASE_B_SLOT_CHECK ({slot_checks})")
    lines.append("")
    lines.append("`define SOC_MANIFEST_ICODE_RV32_EXEC \\")
    for s in active:
        icode = s["targets"][0]["icode"]
        lines.extend([
            f"  soc_manifest_exec_icode(4'd{s['cpu_id']}, `ICODE_{s['name']}_SLOT0_PTR, icode_exec_ok); \\",
            f'  check("Icode RV32 exec {s["name"]} ({icode})", icode_exec_ok); \\',
        ])
    lines.append("")
    lines.append("`define SOC_MANIFEST_ICODE_MAP_BUS_CHECKS \\")
    for s in active:
        for t in s["targets"]:
            macro = f"ICODE_BUS_{t['icode'].upper()}"
            lines.append(
                f'  check("Icode map {t["sym"]}", `{macro} == 32\'h{t["addr"]:08X}); \\'
            )
    lines.append("")
    lines.append("`define SOC_MANIFEST_ICODE_AGENT_ROUNDS \\")
    lines.append("  begin : _manifest_icode_rounds \\")
    lines.append("    integer _slot; \\")
    lines.append(
        "    for (_slot = 0; _slot < `SOC_MANIFEST_MAX_ICODE_SLOTS; _slot = _slot + 1) begin \\"
    )
    lines.append("      if (_slot > 0) begin \\")
    lines.append("        orch_rst_before = orch_reset_count; \\")
    lines.append("        u_orch.icode_inter_reset(); \\")
    lines.extend([
        '        check("Icode inter-reset pulse", orch_reset_count > orch_rst_before); \\',
        "      end \\",
    ])
    for slot in range(max_icode_slots):
        lines.append(f"      if (_slot == {slot}) begin \\")
        for s in slaves:
            gi = s["cpu_id"] - 1
            lines.append(f"        g_slv{gi}.u_bus.u_cpu.sim_stop = 1; \\")
            lines.append(f"        g_slv{gi}.u_bus.u_cpu.request_sim_stop = 0; \\")
        lines.append("        repeat (2) @(posedge soc_clk); \\")
        for s in active:
            if slot < len(s["targets"]):
                addr = s["targets"][slot]["addr"]
                lines.append(
                    f"        manifest_decode_read(32'h{addr:08X}, 3'd4, rdata, rresp, rport); \\"
                )
                lines.append(
                    f"        u_ag_{s['cpu_id']}.run_phase_c_slot(rdata, rresp, _slot); \\"
                )
        if slot == 0 and active:
            round0_sum = " + ".join(f"sl_pass[{s['cpu_id'] - 1}]" for s in active)
            lines.append(
                f'        check("Multi-icode round0 PASS={len(active)}", '
                f"{round0_sum} == {len(active)}); \\"
            )
        lines.append("      end \\")
    lines.extend([
        "    end \\",
        "  end \\",
        "",
    ])
    agent_pass_sum = " + ".join(f"sl_pass[{s['cpu_id'] - 1}]" for s in active) or "0"
    agent_fail_sum = " + ".join(f"sl_fail[{s['cpu_id'] - 1}]" for s in active) or "0"
    lines.extend([
        "`define SOC_MANIFEST_ICODE_FINAL_CHECKS \\",
        f"  total_pass = {agent_pass_sum}; \\",
        f"  total_fail = {agent_fail_sum}; \\",
        '  check("Platform multi-icode PASS", '
        f"total_pass == `SOC_MANIFEST_TOTAL_ICODE_PASS && total_fail == 0); \\",
        "",
    ])
    return lines


def _os_api_supported(bus_type: str, api_key: str) -> bool:
    if api_key.startswith("read"):
        return bus_supports_read_outstanding(bus_type)
    if api_key.startswith("write"):
        return bus_supports_write_outstanding(bus_type)
    return False


def generate_bus_os_bind_vh(
    slaves: list[dict],
    xmr_prefix: str,
    comment: str,
) -> dict[str, str]:
    """Per-API case binds for outstanding bus_* tasks (CPU manifest bind)."""
    out: dict[str, str] = {}
    for api_key, task_name, arglist in OS_BIND_APIS:
        lines = [
            f"// Auto-generated by gen_tb_campaign.py — {comment} {task_name}",
            "        case (CPU_ID)",
        ]
        for s in slaves:
            gi = s["cpu_id"] - 1
            cid = s["cpu_id"]
            path = f"{xmr_prefix}.g_slv{gi}.u_bus.u_bridge"
            bt = normalize_bus_type(s.get("bus_type") or "task")
            if _os_api_supported(bt, api_key):
                lines.append(f"          7'd{cid}: {path}.{task_name}({arglist});")
            elif api_key.endswith("_issue"):
                lines.append(
                    f"          7'd{cid}: begin handle = -1; ok = 1'b0; end"
                )
            elif api_key.endswith("_wait"):
                if api_key.startswith("read"):
                    lines.append(
                        f"          7'd{cid}: begin data = 32'h0; resp = 2'd2; end"
                    )
                else:
                    lines.append(f"          7'd{cid}: resp = 2'd2;")
            elif api_key.endswith("_poll"):
                if api_key.startswith("read"):
                    lines.append(
                        f"          7'd{cid}: begin data = 32'h0; resp = 2'd2; done = 1'b0; end"
                    )
                else:
                    lines.append(
                        f"          7'd{cid}: begin resp = 2'd2; done = 1'b0; end"
                    )
            elif api_key.endswith("_count"):
                lines.append(f"          7'd{cid}: n = 0;")
        if api_key.endswith("_issue"):
            lines.append("          default: begin handle = -1; ok = 1'b0; end")
        elif api_key.endswith("_wait"):
            if api_key.startswith("read"):
                lines.append(
                    "          default: begin data = 32'h0; resp = 2'd2; end"
                )
            else:
                lines.append("          default: resp = 2'd2;")
        elif api_key.endswith("_poll"):
            if api_key.startswith("read"):
                lines.append(
                    "          default: begin data = 32'h0; resp = 2'd2; done = 1'b0; end"
                )
            else:
                lines.append(
                    "          default: begin resp = 2'd2; done = 1'b0; end"
                )
        else:
            lines.append("          default: n = 0;")
        lines.extend(["        endcase", ""])
        out[api_key] = "\n".join(lines)
    return out


def write_bus_os_bind_files(
    slaves: list[dict],
    xmr_prefix: str,
    comment: str,
    prefix: str,
) -> None:
    binds = generate_bus_os_bind_vh(slaves, xmr_prefix, comment)
    for api_key, _task, _args in OS_BIND_APIS:
        path = os.path.join(INCLUDE_DIR, f"verif_{prefix}_soc_bus_{api_key}.vh")
        with open(path, "w", encoding="utf-8") as f:
            f.write(binds[api_key])


def generate_manifest_bus_bind_vh(
    slaves: list[dict],
    module_name: str = "tb_soc_manifest",
) -> tuple[str, str]:
    read_lines = [
        f"// Auto-generated by gen_tb_campaign.py — {module_name} bus_read bind",
        "        case (CPU_ID)",
    ]
    write_lines = [
        f"// Auto-generated by gen_tb_campaign.py — {module_name} bus_write bind",
        "        case (CPU_ID)",
    ]
    for s in slaves:
        gi = s["cpu_id"] - 1
        cid = s["cpu_id"]
        read_lines.append(
            f"          7'd{cid}: {module_name}.g_slv{gi}.u_bus.u_bridge.bus_read(addr, size, data, resp);"
        )
        write_lines.append(
            f"          7'd{cid}: {module_name}.g_slv{gi}.u_bus.u_bridge.bus_write(addr, data, size, resp);"
        )
    read_lines.extend([
        "          default: begin data = 32'h0; resp = 2'd2; end",
        "        endcase",
        "",
    ])
    write_lines.extend([
        "          default: resp = 2'd2;",
        "        endcase",
        "",
    ])
    return "\n".join(read_lines), "\n".join(write_lines)


def generate_soc_manifest_defs_vh(
    cpus: list[dict],
    hierarchy: list[dict],
    manifest_slaves: list[dict],
    pool_bytes: int,
) -> str:
    slaves = soc_manifest_slaves(cpus, hierarchy, manifest_slaves)
    if not slaves:
        slaves = hierarchy[:3]
    n = len(slaves)
    lines = [
        "// Auto-generated by gen_tb_campaign.py — do not edit",
        "`ifndef TB_SOC_MANIFEST_DEFS_VH",
        "`define TB_SOC_MANIFEST_DEFS_VH",
        "",
        f"`define SOC_MANIFEST_NUM_SLAVES {n}",
        "",
    ]
    for s in slaves:
        lines.append(f"`define SOC_MANIFEST_POOL_{s['name']} 32'h{s['pool_word']:08X}")
    lines.append(f"`define SOC_MANIFEST_POOL_ICODE 32'h{POOL_WORD_ICODE:08X}")
    lines.append("")
    lines.extend(emit_soc_manifest_phase_macros(slaves, pool_bytes))
    lines.extend(emit_soc_manifest_phase_a_checks(slaves))
    lines.extend(["`endif", ""])
    return "\n".join(lines)


def generate_soc_manifest_body_vh(
    cpus: list[dict],
    hierarchy: list[dict],
    manifest_slaves: list[dict],
) -> str:
    slaves = soc_manifest_slaves(cpus, hierarchy, manifest_slaves)
    if not slaves:
        slaves = hierarchy[:3]
    wired = _slaves_with_bus_port(slaves)
    n = len(slaves)
    out: list[str] = [
        "// Auto-generated by gen_tb_campaign.py — do not edit",
        "// Included inside module tb_soc_manifest (fabric + cells + CONNECT)",
        "// Edit campaign_slots.yaml / soc_hierarchy*.yaml then: make icodes",
        "",
    ]
    out.extend(emit_soc_manifest_snoop_wires(n))
    if _wired_needs_bus_widths(wired):
        out.extend(emit_bus_soc_width_localparams(wired))
    out.extend(emit_scale_soc_port_wires(wired))
    out.extend(emit_soc_axi_id_assigns(wired))
    out.extend(emit_soc_stub_periph(wired))
    out.extend(emit_soc_manifest_slaves(slaves))
    out.extend(emit_soc_manifest_step_always(slaves))
    out.extend(emit_soc_manifest_agents(slaves))
    out.extend(emit_soc_manifest_setup(slaves))
    out.extend(emit_soc_manifest_run_cpu_task(slaves))
    out.extend(emit_soc_manifest_apply_connects(wired))
    out.append("")
    return "\n".join(out)


def emit_master_vcpu() -> list[str]:
    return [
        "  `ifdef CAMPAIGN_MASTER_VCPU_ENABLED",
        "  verif_cpu_core #(",
        "    .CPU_ID(0), .USE_SHARED_BUS(0), .USE_SHARED_POOL(0), .USE_SOC_BUS(1)",
        "  ) u_mstr_cpu (",
        "    .final_pc(), .total_steps(), .sim_stop(),",
        "    .assert_pass(), .assert_fail(), .bus_txn_count(),",
        "    .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()",
        "  );",
        "  `endif",
        "",
    ]


def emit_master_agent(master: dict | None) -> list[str]:
    if not master or not master.get("targets"):
        return []
    name = master["name"]
    icode_expr = (
        f"`ICODE_{name}_SLOT0_PTR"
        if master.get("targets")
        else "32'h0"
    )
    return [
        "  `ifdef CAMPAIGN_MASTER_HAS_AGENT",
        f"  verif_agent_slave #(.CPU_ID(0), .CPU_NAME(\"{_padded_name(name)}\"), "
        f".TAP_PORT(`CAMPAIGN_MASTER_TAP_PORT)) u_mstr_ag (",
        "    .phase(orch_phase), .boot_fw_offset(orch_boot_fw), .reset_pulse(orch_reset),",
        "    .txn_valid(u_soc.stxn_valid[`CAMPAIGN_MASTER_TAP_PORT]),",
        "    .txn_is_write(u_soc.stxn_wr[`CAMPAIGN_MASTER_TAP_PORT]),",
        "    .txn_addr(u_soc.stxn_addr[`CAMPAIGN_MASTER_TAP_PORT]),",
        "    .txn_data(u_soc.stxn_data[`CAMPAIGN_MASTER_TAP_PORT]),",
        f"    .icode_ptr({icode_expr}), .icode_kind(3'd0),",
        "    .slot_count(mstr_slot_count), .verify_pass(mstr_pass),",
        "    .verify_fail(mstr_fail), .txn_recorded(mstr_txns)",
        "  );",
        "  `endif",
        "",
    ]


def emit_vcpu_generate(max_slots: int) -> list[str]:
    lines = emit_master_vcpu()
    if max_slots <= 0:
        return lines
    lines.extend([
        "  genvar gci;",
        "  generate",
        f"    for (gci = 0; gci < `CAMPAIGN_MAX_SLOTS; gci = gci + 1) begin : g_cpu",
        "      verif_cpu_core #(",
        "        .CPU_ID(gci + 1), .USE_SHARED_BUS(0), .USE_SHARED_POOL(0),"
        " .USE_SOC_BUS(1), .USE_SHARED_SYNC(1), .USE_HW_FORCE(1)",
        "      ) u_cpu (",
        "        .final_pc(), .total_steps(), .sim_stop(),",
        "        .assert_pass(), .assert_fail(), .bus_txn_count(),",
        "        .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()",
        "      );",
        "    end",
        "  endgenerate",
        "",
    ])
    return lines


def _ternary_gi(slaves: list[dict], fmt, default: str) -> str:
    """Right-nested (gi==cpu_id-1)?val:... for generate localparams."""
    expr = default
    for s in reversed(slaves):
        gi = s["cpu_id"] - 1
        expr = f"(gi == {gi}) ? {fmt(s)} : {expr}"
    return expr


def emit_agent_generate(slaves: list[dict], max_slots: int) -> list[str]:
    if max_slots <= 0:
        return []
    tap_expr = _ternary_gi(slaves, lambda s: f"8'd{s['tap']}", "8'd0")
    name_expr = _ternary_gi(slaves, lambda s: f'"{_padded_name(s["name"])}"', '"RESERVED"')
    icode_expr = _ternary_gi(
        slaves,
        lambda s: (
            f"`ICODE_{s['name']}_SLOT0_PTR"
            if s.get("enabled") and s.get("targets")
            else "32'h0"
        ),
        "32'h0",
    )
    lines = [
        "  genvar gi;",
        "  generate",
        f"    for (gi = 0; gi < `CAMPAIGN_MAX_SLOTS; gi = gi + 1) begin : g_ag",
        "      localparam [3:0]  CID = gi + 4'd1;",
        f"      localparam [7:0]  TAP = {tap_expr};",
        f"      localparam [31:0] ICODE_PTR = {icode_expr};",
        f"      localparam [8*8:1] AG_NAME = {name_expr};",
        "      verif_agent_slave #(.CPU_ID(CID), .CPU_NAME(AG_NAME), .TAP_PORT(TAP)) u_ag (",
        "        .phase(orch_phase), .boot_fw_offset(orch_boot_fw), .reset_pulse(orch_reset),",
        "        .txn_valid(u_soc.stxn_valid[TAP]), .txn_is_write(u_soc.stxn_wr[TAP]),",
        "        .txn_addr(u_soc.stxn_addr[TAP]), .txn_data(u_soc.stxn_data[TAP]),",
        "        .icode_ptr(ICODE_PTR), .icode_kind(3'd0),",
        "        .slot_count(sl_slot_count[gi]), .verify_pass(sl_pass[gi]),",
        "        .verify_fail(sl_fail[gi]), .txn_recorded(sl_txns[gi])",
        "      );",
        "    end",
        "  endgenerate",
        "",
    ]
    return lines


def emit_setup_cpu_task(cpus: list[dict]) -> list[str]:
    lines = [
        "  task setup_cpu;",
        "    input [3:0] cid;",
        "    input [8*8:1] name;",
        "    input [31:0] pool_base;",
        "    input [31:0] wdt_to;",
        "    reg [1024*8:1] logpath;",
        "    begin",
        "      case (cid)",
    ]
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.extend([
            f"        4'd{c['id']}: begin",
            f"          {hdl}.cpu_init();",
            f"          {hdl}.cpu_set_name(name);",
            f"          {hdl}.cpu_attach_pool_region(pool_base, FW_SIZE);",
            f"          {hdl}.cpu_attach_recorder();",
            f"          {hdl}.cpu_attach_wdt(wdt_to);",
            f"          {hdl}.cpu_attach_coverage();",
            f"          {hdl}.cpu_attach_wave_dumper();",
            f"          {hdl}.cpu_attach_sync();",
            f"          {hdl}.cpu_set_hierarchy({cpu_hierarchy_hex(c['id'])});",
            f'          $sformat(logpath, "%0s/SCPU{c["id"]}.log", log_dir);',
            f"          {hdl}.cpu_open_dedicated_log(logpath);",
            "        end",
        ])
    lines.extend(["        default: ;", "      endcase", "    end", "  endtask", ""])
    return lines


def _emit_cpu_run_loop(hdl: str) -> list[str]:
    return [
        "          for (step = 0; step < max_steps; step = step + 1) begin",
        f"            if ({hdl}.request_sim_stop || {hdl}.sim_stop)",
        "              step = max_steps;",
        f"            else if ({hdl}.state == `CPU_STATE_SYNC_WAIT)",
        f"              {hdl}.cpu_sync_poll_resume();",
        f"            else if ({hdl}.state == `CPU_STATE_RUNNING ||",
        f"                     {hdl}.state == `CPU_STATE_DUMMY)",
        f"              {hdl}.cpu_step();",
        "          end",
    ]


def emit_run_cpu_task(cpus: list[dict]) -> list[str]:
    uart = next((c for c in cpus if c["role"] == "uart"), None)
    lines = [
        "  task run_cpu_core;",
        "    input [3:0]  cid;",
        "    input [31:0] offset;",
        "    input [31:0] max_steps;",
        "    output       recovered;",
        "    begin",
        "      recovered = 0;",
        "      case (cid)",
    ]
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.append(f"        4'd{c['id']}: begin")
        if uart and c["id"] == uart["id"]:
            lines.extend([
                f"          rec_before = {hdl}.recovery_count;",
                f"          {hdl}.pc = offset;",
                f"          {hdl}.state = `CPU_STATE_RUNNING;",
                f"          {hdl}.request_sim_stop = 0;",
                f"          {hdl}.sim_stop = 0;",
                "          if (offset != OFF_UART_HANG) begin",
                f"            {hdl}.wdt_count = 0;",
                f"            {hdl}.wdt_fired = 0;",
                "          end",
                *_emit_cpu_run_loop(hdl),
                f"          if ({hdl}.recovery_count > rec_before)",
                "            recovered = 1;",
            ])
        else:
            lines.extend([
                f"          {hdl}.pc = offset;",
                f"          {hdl}.state = `CPU_STATE_RUNNING;",
                f"          {hdl}.request_sim_stop = 0;",
                f"          {hdl}.sim_stop = 0;",
                f"          {hdl}.wdt_count = 0;",
                f"          {hdl}.wdt_fired = 0;",
                *_emit_cpu_run_loop(hdl),
            ])
        lines.append("        end")
    lines.extend(["        default: ;", "      endcase", "    end", "  endtask", ""])
    return lines


def emit_run_cpus_parallel_task(cpus: list[dict]) -> list[str]:
    if not cpus:
        return []
    lines = [
        "  task run_cpus_parallel;",
        "    input [31:0] max_steps;",
        "    reg        all_done;",
        "    integer    s;",
        "    begin",
        "      for (s = 0; s < max_steps; s = s + 1) begin",
        "        all_done = 1;",
    ]
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.extend([
            f"        if (!({hdl}.request_sim_stop || {hdl}.sim_stop)) begin",
            f"          if ({hdl}.state == `CPU_STATE_SYNC_WAIT)",
            f"            {hdl}.cpu_sync_poll_resume();",
            f"          if ({hdl}.state == `CPU_STATE_RUNNING ||",
            f"                   {hdl}.state == `CPU_STATE_DUMMY) begin",
            f"            {hdl}.cpu_step();",
            "            all_done = 0;",
            f"          end else if ({hdl}.state == `CPU_STATE_SYNC_WAIT)",
            "            all_done = 0;",
            "        end",
        ])
    lines.extend([
        "        if (all_done) s = max_steps;",
        "      end",
        "    end",
        "  endtask",
        "",
    ])
    return lines


def emit_start_cpus_parallel_task(cpus: list[dict]) -> list[str]:
    if not cpus:
        return []
    lines = [
        "  task start_cpus_parallel;",
        "    input [31:0] offset;",
        "    begin",
    ]
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.extend([
            f"      {hdl}.pc = offset;",
            f"      {hdl}.state = `CPU_STATE_RUNNING;",
            f"      {hdl}.request_sim_stop = 0;",
            f"      {hdl}.sim_stop = 0;",
            f"      {hdl}.wdt_count = 0;",
            f"      {hdl}.wdt_fired = 0;",
        ])
    lines.extend(["    end", "  endtask", ""])
    return lines


def emit_console_cmd_task(cpus: list[dict]) -> list[str]:
    if not cpus:
        return []
    max_cid = max(c["id"] for c in cpus)
    lines = [
        "  // --- EDA interactive console (VCS/Xcelium UCLI while simulation is stopped) ---",
        "  //   call tb_full_campaign.console_help();",
        '  //   call tb_full_campaign.console_cmd(4\'d1, "vsync", 32\'d10, 0, 0);',
        '  //   call tb_full_campaign.console_sync_cmd("sync_configure", 32\'d10, 32\'d7, 0);',
        "  // cid=0 → all active VCPUs; cid 1..N → SCPU id",
        "",
        "  task console_help;",
        "    begin",
        "      $display(\"[Console] tb_full_campaign — call console_cmd / console_sync_cmd\");",
        "      $display(\"  +console_pause  → $stop after VCPU setup (VCS/Xcelium interactive)\");",
        "      console_sync_cmd(\"help\", 0, 0, 0);",
    ]
    for c in cpus:
        lines.append(f"      {cpu_hdl(c['id'])}.cpu_console_help();")
    lines.extend([
        "    end",
        "  endtask",
        "",
        "  task console_sync_cmd;",
        "    input [8*32:1] cmd;",
        "    input [31:0]   a0;",
        "    input [31:0]   a1;",
        "    input [31:0]   a2;",
        "    reg [63:0]     mask;",
        "    begin",
        "      if (cmd == \"help\") begin",
        "        $display(\"[Console] platform commands (sync + hw_force):\");",
        "        $display(\"  sync_configure (a0=id a1=mask_low a2=mask_high)\");",
        "        $display(\"  sync_barrier_count\");",
        "        $display(\"  hw_force_set (a0=hier a1=addr a2=value)\");",
        "        $display(\"  hw_force_release (a0=hier a1=addr)\");",
        "        $display(\"  hw_force_status\");",
        "      end else if (cmd == \"sync_configure\") begin",
        "        mask = {a2, a1};",
        "        u_sync.sync_configure(a0[7:0], mask);",
        "      end else if (cmd == \"sync_barrier_count\")",
        "        $display(\"[Console] sync barrier_release_count=%0d\", u_sync.barrier_release_count);",
        "      else if (cmd == \"hw_force_set\")",
        "        u_hw_force.hw_force_set(a0, a1, a2);",
        "      else if (cmd == \"hw_force_release\")",
        "        u_hw_force.hw_force_clear(a0, a1);",
        "      else if (cmd == \"hw_force_status\")",
        "        $display(\"[Console] hw_force active=%0d set=%0d hit=%0d\",",
        "                 u_hw_force.active_count, u_hw_force.force_set_count, u_hw_force.force_hit_count);",
        "      else",
        "        $display(\"[Console] unknown platform cmd=%0s\", cmd);",
        "    end",
        "  endtask",
        "",
        "  task console_cmd;",
        "    input [3:0]    cid;",
        "    input [8*32:1] cmd;",
        "    input [31:0]   a0;",
        "    input [31:0]   a1;",
        "    input [31:0]   a2;",
        "    begin",
    ])
    for c in cpus:
        cid = c["id"]
        hdl = cpu_hdl(c["id"])
        lines.append(
            f"      if (cid == 0 || cid == {cid}) "
            f"{hdl}.cpu_console_dispatch(cmd, a0, a1, a2);"
        )
    lines.extend([
        f"      if (cid > 4'd{max_cid})",
        f"        $display(\"[Console] unknown cpu_id=%0d (active VCPUs 1..{max_cid})\", cid);",
        "    end",
        "  endtask",
        "",
        "`define CAMPAIGN_CONSOLE_PAUSE \\",
        "  if ($test$plusargs(\"console_pause\")) begin \\",
        "    console_help(); \\",
        "    $display(\"[Console] Paused (+console_pause). iverilog: no UCLI — use VCS/Xcelium.\"); \\",
        "    $stop; \\",
        "  end \\",
        "",
    ])
    return lines


def emit_sync_parallel_macro(cpus: list[dict]) -> list[str]:
    if len(cpus) < 2:
        return [
            "`define CAMPAIGN_SYNC_PARALLEL \\",
            '  $display("\\n[3] Multi-CPU sync skipped (<2 active VCPUs)"); \\',
            "",
        ]
    mask = sync_participant_mask(cpus)
    checks_done = " && ".join(
        f"({cpu_hdl(c['id'])}.request_sim_stop || {cpu_hdl(c['id'])}.sim_stop)"
        for c in cpus
    )
    checks_bus = []
    for i, c in enumerate(cpus):
        hdl = cpu_hdl(c["id"])
        checks_bus.append(
            f'  check_eq("Sync parallel bus {c["name"]}", _sync_bus{i} < {hdl}.bus_txn_count); \\'
        )
    bus_before = []
    for i, c in enumerate(cpus):
        hdl = cpu_hdl(c["id"])
        bus_before.append(f"    _sync_bus{i} = {hdl}.bus_txn_count; \\")
    return [
        f"`define CAMPAIGN_SYNC_BARRIER_ID {CAMPAIGN_SYNC_BARRIER_ID}",
        f"`define CAMPAIGN_SYNC_MASK 64'd{mask}",
        "`define CAMPAIGN_OFF_SYNC_BARRIER 32'h380",
        "`define CAMPAIGN_SYNC_PARALLEL \\",
        "  begin : _sync_parallel \\",
        "    reg [31:0] _rel_before; \\",
        *[f"    reg [31:0] _sync_bus{i}; \\" for i in range(len(cpus))],
        '    $display("\\n[3] Multi-CPU sync barrier + parallel bus (vsync firmware)"); \\',
        "    _rel_before = u_sync.barrier_release_count; \\",
        *bus_before,
        f"    u_sync.sync_configure(8'd{CAMPAIGN_SYNC_BARRIER_ID}, 64'd{mask}); \\",
        "    start_cpus_parallel(`CAMPAIGN_OFF_SYNC_BARRIER); \\",
        "    run_cpus_parallel(800); \\",
        '    check_eq("Sync parallel barrier release", u_sync.barrier_release_count == _rel_before + 1); \\',
        f'    check_eq("Sync parallel firmware done", {checks_done}); \\',
        *checks_bus,
        "  end \\",
        "",
    ]


def emit_scenario_feature_banner() -> list[str]:
    return [
        "// --- example.sh gen default campaign scenario (feature matrix) ---",
        "// Platform: Phase A/B/C orchestrator, master init_done, agent snoop, icode pool",
        "// Custom insn: vstop vwdt vtrace vsync vassert vforce/vrelease vhw_force/vhw_release vwave",
        "// Debug: console stall/resume, WDT hang+recovery+DEADDEAD, unified pool, VCD export",
        "// Sync: parallel vsync barrier @ OFF_SYNC_BARRIER + per-CPU solo vsync in phase_c",
        "",
    ]


def emit_campaign_execute_macro(cpus: list[dict]) -> list[str]:
    sfr = next((c for c in cpus if c["role"] in ("sfr", "solo")), None)
    sfr_hdl = cpu_hdl(sfr["id"]) if sfr else None
    phase_a_bus = (
        f'  check_eq("Phase A bus txn (SFR)", {sfr_hdl}.bus_txn_count >= 1); \\'
        if sfr_hdl else ""
    )
    phase_a_steps = (
        f'  check_eq("Phase A vwdt/vtrace steps", {sfr_hdl}.total_steps >= 4); \\'
        if sfr_hdl else ""
    )
    agent_snoop = (
        "  check_eq(\"Phase A agent snoop\", sl_txns[0] >= 1 && sl_txns[1] >= 1 && sl_txns[2] >= 1); \\"
        if len(cpus) >= 3 else ""
    )
    lines = [
        "`define CAMPAIGN_EXECUTE \\",
        "  `CAMPAIGN_LOAD_FIRMWARE \\",
        "  `CAMPAIGN_SETUP_VCPUS \\",
        "  `CAMPAIGN_CONSOLE_PAUSE \\",
        '  $display("\\n[1] Phase A — SoC init + VCPU + agent snoop"); \\',
        "  u_orch.phase_release(`PHASE_INIT, OFF_A); \\",
        "  u_soc.run_init(); \\",
        "  `CAMPAIGN_RUN_PHASE_A_AGENTS \\",
        "  `CAMPAIGN_RUN_PHASE_A_VCORES \\",
        '  check_eq("Phase A SoC init (17-step)", 1); \\',
        phase_a_bus,
        phase_a_steps,
        agent_snoop,
        '  $display("\\n[2] Phase B — master hints + collect"); \\',
        "  `CAMPAIGN_MASTER_WAIT_INIT_DONE \\",
        "  u_mstr.phase_release(`PHASE_COLLECT, OFF_B); \\",
        "  u_orch.phase_release(`PHASE_COLLECT, OFF_B); \\",
        "  u_mstr.inject_read_hints(); \\",
        "  `CAMPAIGN_MANIFEST_BUS_READS \\",
        "  `CAMPAIGN_RUN_PHASE_B_AGENTS \\",
        "  `CAMPAIGN_RUN_PHASE_B_VCORES \\",
        '  check_eq("Phase B multi-slots (2 per agent)", `CAMPAIGN_PHASE_B_SLOT_CHECK); \\',
        "  `CAMPAIGN_SYNC_PARALLEL \\",
        "  `CAMPAIGN_CONSOLE_STALL \\",
        "  `CAMPAIGN_PHASE_C_SFR \\",
        "  `CAMPAIGN_PHASE_C_SRAM \\",
        '  $display("\\n[6] Platform icode — RV32 pool exec + multi-slot dispatch + inter-reset"); \\',
        "  `CAMPAIGN_ICODE_RV32_EXEC \\",
        "  `CAMPAIGN_ICODE_MAP_BUS_CHECKS \\",
        "  `CAMPAIGN_ICODE_AGENT_ROUNDS \\",
        "  `CAMPAIGN_ICODE_FINAL_CHECKS \\",
        "  `CAMPAIGN_UART_WDT \\",
        '  $display("\\n[8] VCD export"); \\',
        "  `CAMPAIGN_VCD_EXPORT",
        "",
    ]
    return [ln for ln in lines if ln]


def emit_exec_icode_task(cpus: list[dict], use_lazy: bool) -> list[str]:
    if use_lazy:
        icode_setup = [
            "      u_pool.pool_bind_file(cid, icode_pool_path);",
            "      u_pool.pool_assign_region(cid, 32'h0, ICODE_POOL_SZ);",
        ]
    else:
        icode_setup = [
            "      u_pool.pool_use_array(cid);",
            "      u_pool.pool_assign_region(cid, `CAMPAIGN_POOL_WORD_ICODE, ICODE_POOL_SZ);",
        ]
    lines = [
        "  task restore_cpu_pool;",
        "    input [3:0] cid;",
        "    input [31:0] pool_word_base;",
        "    begin",
        "      u_pool.pool_use_array(cid);",
        "      u_pool.pool_assign_region(cid, pool_word_base, FW_SIZE);",
        "    end",
        "  endtask",
        "",
        "  task exec_icode_on_cpu;",
        "    input [3:0]  cid;",
        "    input [31:0] icode_ptr;",
        "    output       ok;",
        "    reg [31:0] txn_before;",
        "    begin",
        "      ok = 0;",
        *icode_setup,
        "      case (cid)",
    ]
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.extend([
            f"        4'd{c['id']}: begin",
            f"          txn_before = {hdl}.bus_txn_count;",
            f"          {hdl}.pc = icode_ptr;",
            f"          {hdl}.state = `CPU_STATE_RUNNING;",
            f"          {hdl}.request_sim_stop = 0;",
            f"          {hdl}.sim_stop = 0;",
            f"          run_cpu_core(cid, icode_ptr, 48, hang_rec);",
            f"          ok = ({hdl}.request_sim_stop || {hdl}.sim_stop)",
            f"               && ({hdl}.bus_txn_count > txn_before);",
            f"          restore_cpu_pool(cid, 32'h{c['pool_word']:x});",
            "        end",
        ])
    lines.extend(["        default: ;", "      endcase", "    end", "  endtask", ""])
    return lines


def emit_pool_policy_macros(pool_bytes: int, use_lazy: bool) -> list[str]:
    mem_words = unified_mem_words(pool_bytes) if not use_lazy else 0x9000
    unified_hex = REL_UNIFIED_HEX
    vcpu_hex = REL_VCPU_HEX
    mode = "lazy (4KiB page file)" if use_lazy else "readmemh (embedded)"
    lines = [
        f"// icode pool {pool_bytes} B — threshold {POOL_READMEMH_MAX_BYTES} B — backing: {mode}",
        f"`define CAMPAIGN_ICODE_POOL_BYTES {pool_bytes}",
        f"`define CAMPAIGN_POOL_READMEMH_MAX 32'h{POOL_READMEMH_MAX_BYTES:08X}",
        f"`define CAMPAIGN_ICODE_USE_LAZY {1 if use_lazy else 0}",
        f"`define CAMPAIGN_MEM_WORDS 32'h{mem_words:x}",
        "",
    ]
    if use_lazy:
        lines.extend([
            "`define CAMPAIGN_LOAD_FIRMWARE \\",
            f'  u_pool.pool_load_hex("{vcpu_hex}"); \\',
            "  `CAMPAIGN_POOL_ASSIGN_VCPUS \\",
            "  u_pool.pool_bind_file(4'd4, icode_pool_path); \\",
            "  u_pool.pool_assign_region(4'd4, 32'h0, ICODE_POOL_SZ); \\",
            "  u_pool.pool_read_word(4'd4, `ICODE_POOL_BASE, pool_word, pool_err); \\",
            '  check_eq("Icode pool file-backed (lazy)", !pool_err && pool_word != 32\'h00000013); \\',
            "",
        ])
    else:
        lines.extend([
            "`define CAMPAIGN_LOAD_FIRMWARE \\",
            f'  u_pool.pool_load_hex("{unified_hex}"); \\',
            "  `CAMPAIGN_POOL_ASSIGN_VCPUS \\",
            "  u_pool.pool_assign_region(4'd4, `CAMPAIGN_POOL_WORD_ICODE, ICODE_POOL_SZ); \\",
            "  u_pool.pool_read_word(4'd4, `ICODE_POOL_BASE, pool_word, pool_err); \\",
            '  check_eq("Icode pool embedded (readmemh)", !pool_err && pool_word != 32\'h00000013); \\',
            "",
        ])
    return lines


def _active_slaves(slaves: list[dict], master: dict | None = None) -> list[dict]:
    return manifest_agents(slaves, master)


def emit_macros(
    cpus: list[dict],
    slaves: list[dict],
    master: dict | None,
    icode_by_name: dict,
    pool_bytes: int,
    use_lazy: bool,
) -> list[str]:
    active = _active_slaves(slaves, master)
    max_icode_slots = max((len(s["targets"]) for s in active), default=0)
    total_pass = sum(len(s["targets"]) for s in active)
    lines = emit_pool_policy_macros(pool_bytes, use_lazy)
    lines.extend([
        f"`define CAMPAIGN_NUM_VCPUS {len(cpus)}",
        f"`define CAMPAIGN_NUM_AGENTS `CAMPAIGN_MAX_SLOTS",
        f"`define CAMPAIGN_MAX_ICODE_SLOTS {max_icode_slots}",
        f"`define CAMPAIGN_TOTAL_ICODE_PASS {total_pass}",
        "",
        "`define CAMPAIGN_POOL_ASSIGN_VCPUS \\",
    ])
    for c in cpus:
        lines.append(f"  u_pool.pool_assign_region({c['id']}, 32'h{c['pool_word']:x}, FW_SIZE); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_SETUP_VCPUS \\")
    for c in cpus:
        lines.append(
            f'  setup_cpu({c["id"]}, "{_padded_name(c["name"])}", 32\'h{c["pool_word"]:x}, 100); \\'
        )
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_A_AGENTS \\")
    for s in active:
        lines.append(f"  {agent_hdl(s['cpu_id'])}.run_phase_a(); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_A_VCORES \\")
    for c in cpus:
        lines.append(f"  run_cpu_core({c['id']}, OFF_A, 64, hang_rec); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_B_AGENTS \\")
    for s in active:
        lines.append(f"  {agent_hdl(s['cpu_id'])}.run_phase_b(); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_B_VCORES \\")
    for c in cpus:
        lines.append(f"  run_cpu_core({c['id']}, OFF_B, 48, hang_rec); \\")
    lines.append("")

    slot_checks = " && ".join(
        f"{agent_slot_count_ref(s['cpu_id'])} >= {len(s['targets'])}" for s in active
    ) or "1"
    lines.append(f"`define CAMPAIGN_PHASE_B_SLOT_CHECK ({slot_checks})")
    lines.append("")

    lines.append("`define CAMPAIGN_ICODE_RV32_EXEC \\")
    for s in active:
        icode = s["targets"][0]["icode"]
        lines.append(
            f"  exec_icode_on_cpu({s['cpu_id']}, `ICODE_{s['name']}_SLOT0_PTR, icode_exec_ok); \\"
        )
        lines.append(
            f'  check_eq("Icode RV32 exec {s["name"]} slot0 ({icode})", icode_exec_ok); \\'
        )
    lines.append("")

    lines.append("`define CAMPAIGN_ICODE_MAP_BUS_CHECKS \\")
    for s in active:
        for t in s["targets"]:
            macro = f"ICODE_BUS_{t['icode'].upper()}"
            lines.append(
                f'  check_eq("Icode map {t["sym"]}", `{macro} == 32\'h{t["addr"]:08X}); \\'
            )
    lines.append("")

    lines.append("`define CAMPAIGN_ICODE_AGENT_ROUNDS \\")
    lines.append("  begin : _gen_icode_rounds \\")
    lines.append("    integer _slot; \\")
    lines.append("    for (_slot = 0; _slot < `CAMPAIGN_MAX_ICODE_SLOTS; _slot = _slot + 1) begin \\")
    lines.append("      if (_slot > 0) begin \\")
    lines.append("        orch_rst_before = orch_reset_count; \\")
    lines.append("        u_orch.icode_inter_reset(); \\")
    lines.append('        check_eq("Icode inter-reset pulse", orch_reset_count > orch_rst_before); \\')
    lines.append("      end \\")
    for slot in range(max_icode_slots):
        lines.append(f"      if (_slot == {slot}) begin \\")
        for s in active:
            if slot < len(s["targets"]):
                addr = s["targets"][slot]["addr"]
                lines.append(
                    f"        u_soc.decode_read(32'h{addr:08X}, 3'd4, rdata, rresp, rport); \\"
                )
                lines.append(
                    f"        {agent_hdl(s['cpu_id'])}.run_phase_c_slot(rdata, rresp, {slot}); \\"
                )
        if slot == 0 and active:
            round0_sum = " + ".join(agent_pass_ref(s["cpu_id"]) for s in active)
            lines.append(
                f'        check_eq("Multi-icode round0 PASS={len(active)}", '
                f"{round0_sum} == {len(active)}); \\"
            )
        lines.append("      end \\")
    lines.append("    end \\")
    lines.append("  end")
    lines.append("")

    agent_pass_sum = " + ".join(agent_pass_ref(s["cpu_id"]) for s in active) or "0"
    agent_fail_sum = " + ".join(agent_fail_ref(s["cpu_id"]) for s in active) or "0"
    lines.append("`define CAMPAIGN_ICODE_FINAL_CHECKS \\")
    lines.append(f"  total_pass = {agent_pass_sum}; \\")
    lines.append(f"  total_fail = {agent_fail_sum}; \\")
    lines.append(
        f'  check_eq("Platform multi-icode PASS={total_pass}", '
        f"total_pass == `CAMPAIGN_TOTAL_ICODE_PASS && total_fail == 0); \\"
    )
    min_orch_resets = 3 + max(0, max_icode_slots - 1)
    lines.append(
        f'  check_eq("Orchestrator reset count", orch_reset_count >= {min_orch_resets}); \\'
    )
    lines.append("")

    return lines


def emit_orchestrator_only_vh(pool_bytes: int, use_lazy: bool, max_slot_count: int) -> str:
    """Minimal TB macros when no VCPU firmware/agents (orchestrator-only solo)."""
    mem_words = unified_mem_words(pool_bytes) if not use_lazy else 0x9000
    mode = "lazy (4KiB page file)" if use_lazy else "readmemh (embedded)"
    hex_path = REL_VCPU_HEX if use_lazy else REL_UNIFIED_HEX
    lines = [
        f"// icode pool {pool_bytes} B — orchestrator-only",
        f"`define CAMPAIGN_ICODE_POOL_BYTES {pool_bytes}",
        f"`define CAMPAIGN_POOL_READMEMH_MAX 32'h{POOL_READMEMH_MAX_BYTES:08X}",
        f"`define CAMPAIGN_ICODE_USE_LAZY {1 if use_lazy else 0}",
        f"`define CAMPAIGN_MEM_WORDS 32'h{mem_words:x}",
        "",
        "`define CAMPAIGN_NUM_VCPUS 0",
        "`define CAMPAIGN_NUM_AGENTS `CAMPAIGN_MAX_SLOTS",
        "`define CAMPAIGN_MAX_ICODE_SLOTS 0",
        "`define CAMPAIGN_TOTAL_ICODE_PASS 0",
        "",
        "`define CAMPAIGN_LOAD_FIRMWARE \\",
        f'  u_pool.pool_load_hex("{hex_path}"); \\',
        "",
    ]
    for macro in (
        "CAMPAIGN_POOL_ASSIGN_VCPUS",
        "CAMPAIGN_SETUP_VCPUS",
        "CAMPAIGN_RUN_PHASE_A_AGENTS",
        "CAMPAIGN_RUN_PHASE_A_VCORES",
        "CAMPAIGN_RUN_PHASE_B_AGENTS",
        "CAMPAIGN_RUN_PHASE_B_VCORES",
        "CAMPAIGN_ICODE_RV32_EXEC",
        "CAMPAIGN_ICODE_MAP_BUS_CHECKS",
        "CAMPAIGN_ICODE_AGENT_ROUNDS",
        "CAMPAIGN_REPORT_VCORES",
        "CAMPAIGN_CLOSE_VCORE_LOGS",
    ):
        lines.extend(_noop_define(macro))
    lines.extend([
        "`define CAMPAIGN_PHASE_B_SLOT_CHECK (1)",
        "",
        "`define CAMPAIGN_ICODE_FINAL_CHECKS \\",
        "  total_pass = 0; \\",
        "  total_fail = 0; \\",
        '  check_eq("Platform multi-icode PASS=0", total_pass == 0 && total_fail == 0); \\',
        '  check_eq("Orchestrator reset count", orch_reset_count >= 2); \\',
        "",
    ])
    lines.extend(_emit_skip_phase_macro(
        "CAMPAIGN_PHASE_C_SFR", "\\n[4] Phase C SFR skipped (orchestrator-only)",
    ))
    lines.extend(_emit_skip_phase_macro(
        "CAMPAIGN_PHASE_C_SRAM", "\\n[5] Phase C SRAM skipped (orchestrator-only)",
    ))
    lines.extend(_emit_skip_phase_macro(
        "CAMPAIGN_UART_WDT", "\\n[7] UART WDT skipped (orchestrator-only)",
    ))
    lines.extend([
        "`define CAMPAIGN_VCD_EXPORT \\",
        '  check_eq("Main VCD path set", 1); \\',
        "",
    ])
    lines.extend(_emit_skip_phase_macro(
        "CAMPAIGN_CONSOLE_STALL", "\\n[3] Console stall skipped (orchestrator-only)",
    ))
    lines.extend(emit_vcpu_generate(max_slot_count))
    lines.extend(emit_agent_generate([], max_slot_count))
    lines.extend(emit_master_wait_init_done_task())
    return "\n".join(lines)


def emit_master_wait_init_done_task() -> list[str]:
    return [
        "  task campaign_master_wait_init_done;",
        "    output ok;",
        "    reg [31:0] rd;",
        "    reg [1:0] rr;",
        "    reg [1:0] rp;",
        "    integer poll;",
        "    begin",
        "      ok = 0;",
        "      if (u_mstr.INIT_DONE_ADDR == 32'h0) begin",
        "        ok = 1;",
        '        $display("SCPU0 (MSTR) > init_done poll disabled (ADDR=0)");',
        "      end else begin",
        '        $display("SCPU0 (MSTR) > polling init_done @0x%08h mask=0x%08h value=0x%08h",',
        "                 u_mstr.INIT_DONE_ADDR, u_mstr.INIT_DONE_MASK, u_mstr.INIT_DONE_VALUE);",
        "        for (poll = 0; poll < u_mstr.INIT_DONE_POLL_MAX; poll = poll + 1) begin",
        "          u_soc.decode_read(u_mstr.INIT_DONE_ADDR, 3'd4, rd, rr, rp);",
        "          if (rr == 2'd0 && u_mstr.init_done_met(rd)) begin",
        "            ok = 1;",
        '            $display("SCPU0 (MSTR) > init_done met @ poll %0d (read=0x%08h)", poll, rd);',
        "            poll = u_mstr.INIT_DONE_POLL_MAX;",
        "          end",
        "        end",
        "        if (!ok)",
        '          $display("SCPU0 (MSTR) > init_done TIMEOUT after %0d polls", u_mstr.INIT_DONE_POLL_MAX);',
        "      end",
        "    end",
        "  endtask",
        "",
        "`define CAMPAIGN_MASTER_WAIT_INIT_DONE \\",
        "  begin : _mstr_wait_init \\",
        "    reg _init_ok; \\",
        "    campaign_master_wait_init_done(_init_ok); \\",
        '    check_eq("Master SoC init_done poll", _init_ok); \\',
        "  end \\",
        "",
    ]


def _emit_skip_phase_macro(name: str, msg: str) -> list[str]:
    return [
        f"`define {name} \\",
        f'  $display("{msg}"); \\',
        "",
    ]


def _noop_define(name: str) -> list[str]:
    """Empty macro — must not end with \\ (swallows the next `define in Verilog)."""
    return [f"`define {name} /* no-op */", ""]


def emit_phase_c_and_uart_macros(cpus: list[dict]) -> list[str]:
    lines = []
    sfr = next((c for c in cpus if c["role"] in ("sfr", "solo")), cpus[0] if cpus else None)
    sram = next((c for c in cpus if c["role"] == "sram"), None)
    uart = next((c for c in cpus if c["role"] == "uart"), None)

    if sfr:
        hdl = cpu_hdl(sfr["id"])
        lines.extend([
            "`define CAMPAIGN_PHASE_C_SFR \\",
            "  $display(\"\\n[4] Phase C — SFR full ISA + DEADDEAD + X/Z\"); \\",
            "  u_orch.phase_release(`PHASE_VERIFY, OFF_C); \\",
            f"  run_cpu_core({sfr['id']}, OFF_C, 900, hang_rec); \\",
            f"  check_eq(\"SFR assertions pass\", {hdl}.assert_fail == 0 && "
            f"{hdl}.assert_pass >= 3); \\",
            f"  check_eq(\"SFR bus activity\", {hdl}.bus_txn_count >= 3); \\",
            f"  check_eq(\"SFR vwave dump\", {hdl}.wave_chg_count > 0); \\",
            f"  check_eq(\"SFR vforce/vdummy/vassert\", {hdl}.assert_pass >= 3); \\",
            f"  check_eq(\"SFR vhw_force hier hit\", {hdl}.hw_force_hit_count >= 1); \\",
            f"  check_eq(\"SFR hw_force table\", u_hw_force.force_set_count >= 1); \\",
            f"  check_eq(\"SFR vsync hits\", {hdl}.sync_arrive_count >= 1); \\",
            f"  check_eq(\"SFR PC coverage\", {hdl}.unique_pcs >= 4); \\",
            "",
        ])
    else:
        lines.extend(_emit_skip_phase_macro(
            "CAMPAIGN_PHASE_C_SFR",
            "\\n[4] Phase C SFR skipped (no SFR/solo VCPU)",
        ))
    if sram:
        hdl = cpu_hdl(sram["id"])
        lines.extend([
            "`define CAMPAIGN_PHASE_C_SRAM \\",
            "  $display(\"\\n[5] Phase C — SRAM JAL/JALR\"); \\",
            f"  run_cpu_core({sram['id']}, OFF_C, 400, hang_rec); \\",
            f"  check_eq(\"SRAM assertions pass\", {hdl}.assert_fail == 0); \\",
            f"  check_eq(\"SRAM JAL/JALR steps\", {hdl}.total_steps >= 10); \\",
            f"  check_eq(\"SRAM vsync hits\", {hdl}.sync_arrive_count >= 1); \\",
            "",
        ])
    else:
        lines.extend(_emit_skip_phase_macro(
            "CAMPAIGN_PHASE_C_SRAM",
            "\\n[5] Phase C SRAM skipped (no SRAM VCPU)",
        ))
    if uart:
        hdl = cpu_hdl(uart["id"])
        lines.extend([
            "`define CAMPAIGN_UART_WDT \\",
            "  $display(\"\\n[7] UART WDT hang → recovery → recover fw\"); \\",
            "  hang_rec = 0; \\",
            f"  run_cpu_core({uart['id']}, OFF_UART_HANG, 200, hang_rec); \\",
            '  check_eq("WDT hang recovery", hang_rec == 1); \\',
            f'  check_eq("WDT fired on hang", {hdl}.recovery_count >= 1); \\',
            f"  run_cpu_core({uart['id']}, OFF_UART_RECOVER, 300, hang_rec); \\",
            f"  check_eq(\"UART recover assertions\", {hdl}.assert_fail == 0); \\",
            f"  check_eq(\"DEADDEAD recovery path\", {hdl}.recovery_count >= 1); \\",
            f"  check_eq(\"UART vsync solo\", {hdl}.sync_arrive_count >= 2); \\",
            "",
        ])
    else:
        lines.extend(_emit_skip_phase_macro(
            "CAMPAIGN_UART_WDT",
            "\\n[7] UART WDT skipped (no UART VCPU)",
        ))

    lines.append("`define CAMPAIGN_VCD_EXPORT \\")
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.append(f'  $sformat(vcd_cpu, "%0s/SCPU{c["id"]}.vcd", log_dir); \\')
        lines.append(f"  {hdl}.wave_export_vcd(vcd_cpu); \\")
    lines.append('  check_eq("Main VCD path set", 1); \\')
    lines.append("")

    lines.append("`define CAMPAIGN_REPORT_VCORES \\")
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        if c["role"] == "uart":
            lines.append(
                f'  $display("  {c["name"]:4s} steps=%0d bus=%0d recov=%0d assert_pass=%0d fail=%0d", '
                f"{hdl}.total_steps, {hdl}.bus_txn_count, "
                f"{hdl}.recovery_count, "
                f"{hdl}.assert_pass, {hdl}.assert_fail); \\"
            )
        else:
            lines.append(
                f'  $display("  {c["name"]:4s} steps=%0d bus=%0d assert_pass=%0d fail=%0d", '
                f"{hdl}.total_steps, {hdl}.bus_txn_count, "
                f"{hdl}.assert_pass, {hdl}.assert_fail); \\"
            )
    lines.append("")

    lines.append("`define CAMPAIGN_CLOSE_VCORE_LOGS \\")
    for c in cpus:
        hdl = cpu_hdl(c["id"])
        lines.append(f"  {hdl}.cpu_close_dedicated_log(); \\")
    lines.append("")

    if sfr:
        console_hdl = cpu_hdl(sfr["id"])
        lines.extend([
            "`define CAMPAIGN_CONSOLE_STALL \\",
            '  $display("\\n[3] Console stall / bus_write / resume"); \\',
            f"  {console_hdl}.cpu_stall(); \\",
            f"  {console_hdl}.cpu_console_bus_write(32'h4000_0008, 32'h0000_CAFE, 3'd4); \\",
            f"  {console_hdl}.cpu_resume(); \\",
            f"  check_eq(\"Console stall/resume\", {console_hdl}.state == `CPU_STATE_RUNNING); \\",
            "",
        ])
    else:
        lines.extend([
            "`define CAMPAIGN_CONSOLE_STALL \\",
            '  $display("\\n[3] Console stall skipped (no SFR/solo VCPU)"); \\',
            "",
        ])
    return lines


def generate_vh(
    cpus: list[dict],
    slaves: list[dict],
    master: dict | None,
    icode_by_name: dict,
    pool_bytes: int,
    use_lazy: bool,
    max_slot_count: int,
) -> str:
    out: list[str] = [
        "// Auto-generated by gen_tb_campaign.py — do not edit",
        "`ifndef TB_FULL_CAMPAIGN_GEN_VH",
        "`define TB_FULL_CAMPAIGN_GEN_VH",
        "",
        "`include \"campaign_scale.vh\"",
        "",
    ]
    out.extend(emit_macros(cpus, slaves, master, icode_by_name, pool_bytes, use_lazy))
    out.extend(emit_scenario_feature_banner())
    out.extend(emit_phase_c_and_uart_macros(cpus))
    out.extend(emit_sync_parallel_macro(cpus))
    out.extend(emit_campaign_execute_macro(cpus))
    out.extend(emit_vcpu_generate(max_slot_count))
    out.extend(emit_master_agent(master))
    out.extend(emit_agent_generate(slaves, max_slot_count))
    out.extend(emit_setup_cpu_task(cpus))
    out.extend(emit_run_cpu_task(cpus))
    out.extend(emit_start_cpus_parallel_task(cpus))
    out.extend(emit_run_cpus_parallel_task(cpus))
    out.extend(emit_console_cmd_task(cpus))
    out.extend(emit_master_wait_init_done_task())
    out.extend(emit_exec_icode_task(cpus, use_lazy))
    out.extend(["`endif", ""])
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate tb_full_campaign_gen.vh and chip-top VH")
    ap.add_argument(
        "--yaml",
        type=str,
        default=None,
        help=f"SoC hierarchy YAML for chip_top gen (default: {SOC_HIER_YAML})",
    )
    args = ap.parse_args()
    soc_hier_yaml = args.yaml or SOC_HIER_YAML

    if not os.path.isfile(ICODE_JSON):
        print(f"[gen_tb] missing {ICODE_JSON} — run build_icode_pool.py first", file=sys.stderr)
        return 1

    all_cpus = parse_cpus_mk(CPUS_MK)
    slaves, master = parse_manifest(MANIFEST_HDR)
    cpus = [c for c in all_cpus if c.get("enabled", 1)]
    icode_by_name = load_icode_map(ICODE_JSON)
    pool_bytes = load_pool_bytes(ICODE_JSON)
    use_lazy = icode_use_lazy(pool_bytes)
    max_slot_count = policy_max_slots()

    if not os.path.isfile(SCALE_VH):
        print(f"[gen_tb] missing {SCALE_VH} — run: make config", file=sys.stderr)
        return 1

    agents = manifest_agents(slaves, master)
    orchestrator_only = not cpus and not agents
    if orchestrator_only:
        print("[gen_tb] orchestrator-only layout (no VCPU FW/agents) — minimal TB macros")
    for s in agents:
        for t in s.get("targets") or []:
            if t["icode"] not in icode_by_name:
                print(f"[gen_tb] WARN icode '{t['icode']}' not in icode_map.json", file=sys.stderr)

    if orchestrator_only:
        body = emit_orchestrator_only_vh(pool_bytes, use_lazy, max_slot_count)
        text = "\n".join([
            "// Auto-generated by gen_tb_campaign.py — do not edit",
            "`ifndef TB_FULL_CAMPAIGN_GEN_VH",
            "`define TB_FULL_CAMPAIGN_GEN_VH",
            "",
            "`include \"campaign_scale.vh\"",
            "",
            body,
            "`endif",
            "",
        ])
    else:
        text = generate_vh(
            cpus, slaves, master, icode_by_name, pool_bytes, use_lazy, max_slot_count
        )
    os.makedirs(os.path.dirname(OUT_VH), exist_ok=True)
    with open(OUT_VH, "w", encoding="utf-8") as f:
        f.write(text)
    mode = "lazy" if use_lazy else "readmemh"
    active_agents = len(agents)
    print(f"[gen_tb] Wrote {OUT_VH} ({max_slot_count} slots, {len(cpus)} active VCPUs, "
          f"{active_agents} campaign agents, pool={pool_bytes}B → {mode})")

    hierarchy = load_soc_hierarchy_yaml(soc_hier_yaml)
    soc_n = soc_manifest_slaves(cpus, hierarchy, slaves)
    soc_defs = generate_soc_manifest_defs_vh(cpus, hierarchy, slaves, pool_bytes)
    with open(OUT_SOC_MANIFEST_DEFS_VH, "w", encoding="utf-8") as f:
        f.write(soc_defs)
    soc_body = generate_soc_manifest_body_vh(cpus, hierarchy, slaves)
    with open(OUT_SOC_MANIFEST_VH, "w", encoding="utf-8") as f:
        f.write(soc_body)
    wired = manifest_wired_slaves(slaves)
    bind_slaves = merge_bind_slaves(soc_n, wired)
    bus_read, bus_write = generate_manifest_bus_bind_vh(soc_n, "tb_soc_manifest")
    with open(OUT_MANIFEST_BUS_READ_VH, "w", encoding="utf-8") as f:
        f.write(bus_read)
    with open(OUT_MANIFEST_BUS_WRITE_VH, "w", encoding="utf-8") as f:
        f.write(bus_write)
    write_bus_os_bind_files(
        soc_n, "tb_soc_manifest", "tb_soc_manifest", "manifest"
    )
    scale_read, scale_write = generate_manifest_bus_bind_vh(
        soc_n, "tb_soc_manifest_scale"
    )
    with open(OUT_MANIFEST_SCALE_BUS_READ_VH, "w", encoding="utf-8") as f:
        f.write(scale_read)
    with open(OUT_MANIFEST_SCALE_BUS_WRITE_VH, "w", encoding="utf-8") as f:
        f.write(scale_write)
    write_bus_os_bind_files(
        soc_n, "tb_soc_manifest_scale", "tb_soc_manifest_scale", "manifest_scale"
    )

    decode_vh = generate_manifest_decode_vh(soc_n, hierarchy)
    with open(OUT_MANIFEST_DECODE_VH, "w", encoding="utf-8") as f:
        f.write(decode_vh)

    if hierarchy:
        chip_read, chip_write = generate_bus_bind_vh(
            hierarchy,
            "chip_top_example",
            "chip_top_example bus_read (VERIF_CHIP_SOC_TB)",
            "chip_top_example bus_write (VERIF_CHIP_SOC_TB)",
        )
        with open(OUT_CHIP_BUS_READ_VH, "w", encoding="utf-8") as f:
            f.write(chip_read)
        with open(OUT_CHIP_BUS_WRITE_VH, "w", encoding="utf-8") as f:
            f.write(chip_write)
        write_bus_os_bind_files(
            hierarchy, "chip_top_example", "chip_top_example", "chip"
        )
        chip_gen = generate_chip_top_gen_vh(hierarchy)
        with open(OUT_CHIP_TOP_GEN_VH, "w", encoding="utf-8") as f:
            f.write(chip_gen)
        chip_decode = generate_chip_decode_vh(hierarchy)
        with open(OUT_CHIP_DECODE_VH, "w", encoding="utf-8") as f:
            f.write(chip_decode)
        with open(OUT_CHIP_TOP_RTL_MK, "w", encoding="utf-8") as f:
            f.write(emit_chip_top_rtl_mk(hierarchy))
        write_chip_soc_cell(hierarchy)
        print(f"[gen_tb] Wrote chip_top bind + {os.path.basename(OUT_CHIP_TOP_GEN_VH)} "
              f"+ decode + {os.path.basename(OUT_CHIP_TOP_RTL_MK)} "
              f"+ {os.path.basename(OUT_CHIP_SOC_CELL)} ({len(hierarchy)} hierarchy cell(s))")

    print(f"[gen_tb] Wrote {OUT_SOC_MANIFEST_DEFS_VH} + {OUT_SOC_MANIFEST_VH} "
          f"+ decode + manifest bus bind ({len(bind_slaves)} bind slot(s), "
          f"{len(soc_n)} SoC cell(s))")

    scale_wired = manifest_wired_slaves(soc_n)
    scale_defs = generate_soc_manifest_scale_defs_vh(scale_wired)
    with open(OUT_SOC_MANIFEST_SCALE_DEFS_VH, "w", encoding="utf-8") as f:
        f.write(scale_defs)
    scale_body = generate_soc_manifest_scale_body_vh(scale_wired, soc_n)
    with open(OUT_SOC_MANIFEST_SCALE_VH, "w", encoding="utf-8") as f:
        f.write(scale_body)
    print(f"[gen_tb] Wrote {OUT_SOC_MANIFEST_SCALE_DEFS_VH} + scale gen "
          f"({len(scale_wired)} wired cell(s), max gi={max((s['cpu_id'] for s in scale_wired), default=0)})")

    return 0


if __name__ == "__main__":
    sys.exit(main())