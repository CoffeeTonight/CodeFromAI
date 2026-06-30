"""AMBA bus signal SSOT for Integration Studio — matches verif_amba_connect_macros.vh."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LEGACY_ALIASES = {"apb": "apb3", "ahb": "ahb_lite", "axi": "axi4lite"}


@dataclass(frozen=True)
class BusSignal:
    suffix: str
    width: int | str
    direction: str  # to_soc | from_soc
    group: str
    note: str = ""

    def default_soc_name(self, prefix: str) -> str:
        return f"{prefix}_{self.suffix}"

    def to_dict(self, prefix: str) -> dict[str, Any]:
        return {
            "suffix": self.suffix,
            "width": self.width,
            "direction": self.direction,
            "group": self.group,
            "note": self.note,
            "verif_port": self.suffix,
            "default_soc": self.default_soc_name(prefix),
            "dir_label": "VerifCPU → SoC" if self.direction == "to_soc" else "SoC → VerifCPU",
        }


def _sig(
    suffix: str,
    width: int | str,
    direction: str,
    group: str,
    note: str = "",
) -> BusSignal:
    return BusSignal(suffix=suffix, width=width, direction=direction, group=group, note=note)


def _apb_core() -> list[BusSignal]:
    return [
        _sig("PADDR", 32, "to_soc", "APB", "address"),
        _sig("PSEL", 1, "to_soc", "APB"),
        _sig("PENABLE", 1, "to_soc", "APB"),
        _sig("PWRITE", 1, "to_soc", "APB"),
        _sig("PWDATA", 32, "to_soc", "APB", "write data"),
        _sig("PSTRB", 4, "to_soc", "APB", "write strobes (APB3+)"),
        _sig("PRDATA", 32, "from_soc", "APB", "read data"),
        _sig("PREADY", 1, "from_soc", "APB", "slave ready (APB3+)"),
        _sig("PSLVERR", 1, "from_soc", "APB", "slave error (APB3+)"),
    ]


def _ahb_lite_core() -> list[BusSignal]:
    return [
        _sig("HADDR", 32, "to_soc", "AHB", "address"),
        _sig("HSIZE", 3, "to_soc", "AHB", "transfer size"),
        _sig("HTRANS", 2, "to_soc", "AHB", "transfer type"),
        _sig("HWRITE", 1, "to_soc", "AHB"),
        _sig("HWDATA", 32, "to_soc", "AHB", "write data"),
        _sig("HREADY", 1, "from_soc", "AHB", "slave ready → master (SOC HREADYOUT)"),
        _sig("HRDATA", 32, "from_soc", "AHB", "read data"),
        _sig("HREADYOUT", 1, "from_soc", "AHB", "alias: slave ready out"),
        _sig("HRESP", 2, "from_soc", "AHB", "response"),
    ]


def _axi_lite_core() -> list[BusSignal]:
    return [
        _sig("arvalid", 1, "to_soc", "AR", "read address valid"),
        _sig("araddr", 32, "to_soc", "AR", "read address"),
        _sig("arsize", 3, "to_soc", "AR", "read size"),
        _sig("arready", 1, "from_soc", "AR", "slave ready for AR"),
        _sig("rvalid", 1, "from_soc", "R", "read data valid"),
        _sig("rdata", 32, "from_soc", "R", "read data"),
        _sig("rresp", 2, "from_soc", "R", "read response"),
        _sig("rready", 1, "to_soc", "R", "master ready for R"),
        _sig("awvalid", 1, "to_soc", "AW", "write address valid"),
        _sig("awaddr", 32, "to_soc", "AW", "write address"),
        _sig("awsize", 3, "to_soc", "AW", "write size"),
        _sig("awready", 1, "from_soc", "AW", "slave ready for AW"),
        _sig("wvalid", 1, "to_soc", "W", "write data valid"),
        _sig("wdata", 32, "to_soc", "W", "write data"),
        _sig("wstrb", 4, "to_soc", "W", "write strobes"),
        _sig("wready", 1, "from_soc", "W", "slave ready for W"),
        _sig("bvalid", 1, "from_soc", "B", "write response valid"),
        _sig("bresp", 2, "from_soc", "B", "write response"),
        _sig("bready", 1, "to_soc", "B", "master ready for B"),
    ]


def _axi_full_extra() -> list[BusSignal]:
    return [
        _sig("arid", 4, "to_soc", "AR", "read ID"),
        _sig("arlen", 8, "to_soc", "AR", "burst length"),
        _sig("arburst", 2, "to_soc", "AR", "burst type"),
        _sig("rid", 4, "from_soc", "R", "read ID"),
        _sig("rlast", 1, "from_soc", "R", "read last"),
        _sig("awid", 4, "to_soc", "AW", "write ID"),
        _sig("awlen", 8, "to_soc", "AW", "burst length"),
        _sig("awburst", 2, "to_soc", "AW", "burst type"),
        _sig("wid", 4, "to_soc", "W", "write ID (AXI3)"),
        _sig("wlast", 1, "to_soc", "W", "write last"),
        _sig("bid", 4, "from_soc", "B", "write response ID"),
    ]


BUS_SIGNAL_SPECS: dict[str, list[BusSignal]] = {
    "apb2": [
        _sig("PADDR", 32, "to_soc", "APB"),
        _sig("PSEL", 1, "to_soc", "APB"),
        _sig("PENABLE", 1, "to_soc", "APB"),
        _sig("PWRITE", 1, "to_soc", "APB"),
        _sig("PWDATA", 32, "to_soc", "APB"),
        _sig("PRDATA", 32, "from_soc", "APB"),
    ],
    "apb3": _apb_core(),
    "apb4": _apb_core() + [_sig("PPROT", 3, "to_soc", "APB", "protection")],
    "apb5": _apb_core()
    + [_sig("PPROT", 3, "to_soc", "APB"), _sig("PWAKEUP", 1, "to_soc", "APB", "wakeup")],
    "ahb_lite": _ahb_lite_core(),
    "ahb5_lite": _ahb_lite_core()
    + [
        _sig("HNONSEC", 1, "to_soc", "AHB", "non-secure"),
        _sig("HEXCL", 1, "to_soc", "AHB", "exclusive"),
        _sig("HEXOK", 1, "from_soc", "AHB", "exclusive okay"),
    ],
    "ahb": _ahb_lite_core()
    + [
        _sig("HNONSEC", 1, "to_soc", "AHB"),
        _sig("HEXCL", 1, "to_soc", "AHB"),
        _sig("HEXOK", 1, "from_soc", "AHB"),
        _sig("HBURST", 3, "to_soc", "AHB", "burst"),
        _sig("HPROT", 4, "to_soc", "AHB", "protection"),
        _sig("HMASTLOCK", 1, "to_soc", "AHB", "lock"),
    ],
    "axi4lite": _axi_lite_core(),
    "axi3full": _axi_lite_core() + _axi_full_extra(),
    "axi4full": _axi_lite_core()
    + [s for s in _axi_full_extra() if s.suffix != "wid"]
    + [
        _sig("arqos", 4, "to_soc", "AR", "QoS"),
        _sig("arregion", 4, "to_soc", "AR", "region"),
        _sig("awqos", 4, "to_soc", "AW", "QoS"),
        _sig("awregion", 4, "to_soc", "AW", "region"),
    ],
    "axi5full": _axi_lite_core()
    + [s for s in _axi_full_extra() if s.suffix != "wid"]
    + [
        _sig("arqos", 4, "to_soc", "AR"),
        _sig("arregion", 4, "to_soc", "AR"),
        _sig("awqos", 4, "to_soc", "AW"),
        _sig("awregion", 4, "to_soc", "AW"),
        _sig("awatop", 6, "to_soc", "AW", "atomic operation"),
    ],
}

BUS_TYPE_LABELS: dict[str, str] = {
    "apb2": "APB2",
    "apb3": "APB3",
    "apb4": "APB4",
    "apb5": "APB5",
    "ahb_lite": "AHB-Lite",
    "ahb5_lite": "AHB5-Lite",
    "ahb": "AHB full",
    "axi4lite": "AXI4-Lite",
    "axi3full": "AXI3 full",
    "axi4full": "AXI4 full",
    "axi5full": "AXI5 full",
}


def normalize_bus_type(name: str) -> str:
    key = name.strip().lower().replace("-", "_")
    return LEGACY_ALIASES.get(key, key)


def bus_signals_for(bus_type: str, prefix: str = "") -> dict[str, Any]:
    key = normalize_bus_type(bus_type)
    specs = BUS_SIGNAL_SPECS.get(key)
    if specs is None:
        return {
            "ok": False,
            "bus_type": key,
            "error": f"unsupported bus_type: {bus_type}",
            "supported": sorted(BUS_SIGNAL_SPECS.keys()),
        }
    pref = prefix.strip()
    signals = [s.to_dict(pref) for s in specs]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in signals:
        groups.setdefault(row["group"], []).append(row)
    return {
        "ok": True,
        "bus_type": key,
        "bus_label": BUS_TYPE_LABELS.get(key, key),
        "prefix": pref,
        "signal_count": len(signals),
        "signals": signals,
        "groups": groups,
        "hint": (
            "Enter your SoC interconnect signal names in the right column. "
            "Default is {prefix}_{suffix} from CONNECT macro."
        ),
    }


def list_supported_bus_types() -> list[dict[str, str]]:
    return [
        {"key": k, "label": BUS_TYPE_LABELS.get(k, k), "aliases": []}
        for k in sorted(BUS_SIGNAL_SPECS.keys())
    ]