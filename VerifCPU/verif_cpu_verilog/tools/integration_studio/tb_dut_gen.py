"""Generate tb_dut_* Verilog fabric from Integration Studio hierarchy JSON."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from amba_signals import bus_signals_for, normalize_bus_type


def _slug(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "fabric"


def _hex32(v: Any) -> str:
    if isinstance(v, int):
        return f"32'h{v:08X}"
    s = str(v or "0").strip().lower()
    if s.startswith("0x"):
        return f"32'h{int(s, 16):08X}"
    if s.isdigit():
        return f"32'h{int(s):08X}"
    return "32'h00000000"


def _norm_slaves(slaves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in slaves:
        if not raw.get("wired", True):
            continue
        port = str(raw.get("bus_port") or "").strip()
        bt = str(raw.get("bus_type") or "axi").strip().lower()
        if bt in ("task", "none", "") or not port:
            continue
        smap = raw.get("signal_map") or {}
        out.append({
            "name": str(raw.get("name") or f"SLV{raw.get('cpu_id')}"),
            "cpu_id": int(raw["cpu_id"]),
            "tap_port": int(raw.get("tap_port", int(raw["cpu_id"]) - 1)),
            "bus_type": bt,
            "bus_port": port,
            "addr_base": raw.get("addr_base", 0),
            "addr_size": raw.get("addr_size", 0x1000),
            "signal_map": {str(k): str(v).strip() for k, v in smap.items() if str(v).strip()},
        })
    out.sort(key=lambda s: s["cpu_id"])
    return out


def _import_campaign(rtl_root: Path):
    campaign = rtl_root / "firmware" / "campaign"
    if not campaign.is_dir():
        raise FileNotFoundError(f"campaign dir missing: {campaign}")
    if str(campaign) not in sys.path:
        sys.path.insert(0, str(campaign))
    import gen_tb_campaign as gtc  # noqa: WPS433
    from gen_soc_bus_connect import emit_connect_vh  # noqa: WPS433

    return gtc, emit_connect_vh


def _slave_has_custom_map(slave: dict[str, Any]) -> bool:
    info = bus_signals_for(slave["bus_type"], slave["bus_port"])
    if not info.get("ok"):
        return False
    smap = slave.get("signal_map") or {}
    for sig in info["signals"]:
        soc = smap.get(sig["suffix"], sig["default_soc"]).strip()
        if soc != sig["default_soc"]:
            return True
    return False


def _emit_custom_bus_wires(slave: dict[str, Any]) -> list[str]:
    info = bus_signals_for(slave["bus_type"], slave["bus_port"])
    if not info.get("ok"):
        return []
    smap = slave.get("signal_map") or {}
    singles: list[str] = []
    buses: dict[str, list[str]] = {}
    lines = [f"  // {slave['name']} — map to your SoC interconnect", ""]
    for sig in info["signals"]:
        soc = smap.get(sig["suffix"], sig["default_soc"]).strip()
        w = str(sig["width"])
        if w == "1":
            singles.append(soc)
        else:
            buses.setdefault(w, []).append(soc)
    for w in sorted(buses, key=lambda x: int(x)):
        names = buses[w]
        lines.append(f"  wire [{w}-1:0] {', '.join(names)};")
    for n in singles:
        lines.append(f"  wire {n};")
    lines.append("")
    return lines


def _emit_custom_connects(slave: dict[str, Any]) -> list[str]:
    info = bus_signals_for(slave["bus_type"], slave["bus_port"])
    if not info.get("ok"):
        return []
    smap = slave.get("signal_map") or {}
    gi = slave["cpu_id"] - 1
    cell = f"g_slv{gi}.u_bus"
    lines = [f"  // {slave['name']} — custom SoC signal connects", ""]
    for sig in info["signals"]:
        soc = smap.get(sig["suffix"], sig["default_soc"]).strip()
        port = sig["suffix"]
        if sig["direction"] == "to_soc":
            lines.append(f"  assign {soc} = {cell}.{port};")
        else:
            lines.append(f"  assign {cell}.{port} = {soc};")
    lines.append("")
    return lines


def _inst_comment(module_name: str, slaves: list[dict[str, Any]]) -> list[str]:
    lines = [
        "// Instantiate in your customer chip top:",
        "//",
        f"//   {module_name} u_verif_dut (",
        "//     .soc_clk  (clk),",
        "//     .soc_rstn (rst_n)",
        "//   );",
        "//",
        "// Tie your interconnect slave/master ports to the bus wires below",
        "// (prefix must match hierarchy bus_port), then:",
        "//   `include \"verif_amba_connect_macros.vh\"",
        "//   `APPLY_ALL_SOC_BUS_CONNECTS;",
    ]
    if slaves:
        lines.append("// Bus wiring summary:")
        for s in slaves:
            lines.append(
                f"//   {s['name']:8s} cpu_id={s['cpu_id']:2d}  "
                f"{normalize_bus_type(s['bus_type']):10s}  prefix={s['bus_port']}"
            )
            info = bus_signals_for(s["bus_type"], s["bus_port"])
            if info.get("ok"):
                smap = s.get("signal_map") or {}
                for sig in info["signals"]:
                    soc = smap.get(sig["suffix"], sig["default_soc"]).strip()
                    lines.append(f"//       {soc}  ({sig['dir_label']}, {sig['suffix']})")
    return lines


def generate_tb_dut_module(
    soc_name: str,
    module_name: str | None,
    slaves: list[dict[str, Any]],
    *,
    rtl_root: Path,
    include_pool: bool = True,
    include_agents: bool = False,
) -> str:
    wired = _norm_slaves(slaves)
    mod = module_name or f"tb_dut_{_slug(soc_name)}"
    gtc, emit_connect_vh = _import_campaign(rtl_root)

    max_gi = max((s["cpu_id"] for s in wired), default=1)
    macro_slaves = [s for s in wired if not _slave_has_custom_map(s)]
    custom_slaves = [s for s in wired if _slave_has_custom_map(s)]
    connect_vh = emit_connect_vh(macro_slaves, "integration_studio hierarchy")
    skip_prefixes = (
        "`ifndef",
        "`define VERIF_SOC",
        "`include",
        "// Auto-generated by gen_soc_bus_connect",
        "// Source:",
    )
    connect_body = "\n".join(
        ln
        for ln in connect_vh.splitlines()
        if ln != "`endif" and not any(ln.startswith(p) for p in skip_prefixes)
    )

    lines: list[str] = [
        "// ============================================================================",
        "// Generated by VERIF-CPU-SOC Integration Studio — TB_DUT fabric",
        f"// soc_name: {soc_name}",
        "//",
        *_inst_comment(mod, wired),
        "// ============================================================================",
        "",
        "`timescale 1ns/1ps",
        "`include \"verif_cpu_defs.vh\"",
        "`include \"verif_platform_defs.vh\"",
        "`include \"verif_amba_connect_macros.vh\"",
        "",
        connect_body,
        "",
        f"module {mod} (",
        "  input wire soc_clk,",
        "  input wire soc_rstn",
        ");",
        "",
    ]

    if include_pool:
        lines.extend([
            "  verif_cpu_unified_pool #(.MEM_WORDS(32'h1000)) u_pool ();",
            "",
        ])

    lines.extend(gtc.emit_chip_top_snoop_wires(max_gi))
    if macro_slaves:
        lines.extend(gtc.emit_scale_soc_port_wires(macro_slaves))
    for s in custom_slaves:
        lines.extend(_emit_custom_bus_wires(s))
    lines.extend(gtc.emit_chip_top_cells(wired))

    if include_agents:
        lines.extend(gtc.emit_chip_agents(wired))

    lines.append("  // Connect VerifCPU bus cells to SoC interconnect wires")
    if macro_slaves:
        lines.append("  `APPLY_ALL_SOC_BUS_CONNECTS;")
    for s in custom_slaves:
        lines.extend(_emit_custom_connects(s))
    lines.extend(["", "endmodule", ""])
    return "\n".join(lines)