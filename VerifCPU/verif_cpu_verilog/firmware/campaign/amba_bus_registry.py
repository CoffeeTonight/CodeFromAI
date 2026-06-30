"""AMBA / SoC bus type registry — SSOT for manifest, CLI, and connect VH generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# SoC interconnect widths — edit here, then: make -C firmware/campaign icodes && make soc_cell
ADDR_WIDTH_DEFAULT = 32
DATA_WIDTH_DEFAULT = 32
AXI_ID_WIDTH_DEFAULT = 4
AXI_MAX_OUTSTANDING_DEFAULT = 4
AHB_MAX_OUTSTANDING_DEFAULT = 4
CHI_MAX_OUTSTANDING_DEFAULT = 4
AXI_LITE_MAX_OUTSTANDING_DEFAULT = 1

# Bus types exposing non-blocking bus_*_issue/wait/poll on the bridge
BUS_READ_OUTSTANDING_TYPES: frozenset[str] = frozenset({
    "axi3full", "axi4full", "axi5full", "ace", "ahb", "chi", "axi4lite",
})
BUS_WRITE_OUTSTANDING_TYPES: frozenset[str] = frozenset({
    "axi3full", "axi4full", "axi5full", "ace", "ahb", "chi", "axi4lite",
})

# AXI4-Stream (when integrated)
AXIS_DATA_WIDTH_DEFAULT = DATA_WIDTH_DEFAULT

# CHI packet flit placeholders (manifest/smoke — match your ICN spec)
CHI_TXREQ_FLIT_WIDTH_DEFAULT = 44
CHI_TXRSP_FLIT_WIDTH_DEFAULT = 13
CHI_TXDAT_FLIT_WIDTH_DEFAULT = 146

# NoC NIU vendor placeholder
NIU_FLIT_WIDTH_DEFAULT = 64


def strb_width(data_width: int = DATA_WIDTH_DEFAULT) -> int:
    return data_width // 8


def addr_range(addr_width: int = ADDR_WIDTH_DEFAULT) -> str:
    return f"[{addr_width - 1}:0]"


def data_range(data_width: int = DATA_WIDTH_DEFAULT) -> str:
    return f"[{data_width - 1}:0]"


def strb_range(data_width: int = DATA_WIDTH_DEFAULT) -> str:
    return f"[{strb_width(data_width) - 1}:0]"


def axi_id_range(id_width: int = AXI_ID_WIDTH_DEFAULT) -> str:
    return f"[{id_width - 1}:0]"


def axi_id_zero(id_width: int = AXI_ID_WIDTH_DEFAULT) -> str:
    return (
        f"{{VERIF_AXI_ID_WIDTH{{1'b0}}}}"
        if id_width == AXI_ID_WIDTH_DEFAULT
        else f"{{{id_width}{{1'b0}}}}"
    )


@dataclass(frozen=True)
class BusTypeSpec:
    """One connectable or manifest-registered bus profile."""

    key: str
    label: str
    amba_family: str
    port_fmt: str | None = None
    connect_kind: str | None = None
    rtl_module: str | None = None
    rtl_status: str = "planned"
    cli_flags: tuple[str, ...] = ()
    notes: str = ""


    @property
    def manifest_only(self) -> bool:
        return self.rtl_status not in ("done", "smoke")


def _spec(
    key: str,
    label: str,
    family: str,
    *,
    port_fmt: str | None = None,
    connect: str | None = None,
    rtl: str | None = None,
    status: str = "planned",
    cli: tuple[str, ...] = (),
    notes: str = "",
) -> BusTypeSpec:
    return BusTypeSpec(
        key=key,
        label=label,
        amba_family=family,
        port_fmt=port_fmt,
        connect_kind=connect,
        rtl_module=rtl,
        rtl_status=status,
        cli_flags=cli or (f"--{key}",),
        notes=notes,
    )


# fmt: off
BUS_TYPES: dict[str, BusTypeSpec] = {
    "task": _spec("task", "Campaign task bus (simple_soc)", "verif",
                  status="done", cli=("--task",), notes="Campaign TB only"),
    "none": _spec("none", "Reserved / unwired", "verif", status="done"),

    "apb2": _spec("apb2", "APB2", "amba", port_fmt="S{:02d}_APB",
                  connect="apb2", rtl="verif_apb2_master", status="smoke",
                  cli=("--apb2",)),
    "apb3": _spec("apb3", "APB3", "amba", port_fmt="S{:02d}_APB",
                  connect="apb3", rtl="verif_apb_master", status="done",
                  cli=("--apb3", "--apb")),
    "apb4": _spec("apb4", "APB4", "amba", port_fmt="S{:02d}_APB",
                  connect="apb4", rtl="verif_apb4_master", status="smoke",
                  cli=("--apb4",)),
    "apb5": _spec("apb5", "APB5", "amba", port_fmt="S{:02d}_APB",
                  connect="apb5", rtl="verif_apb5_master", status="smoke",
                  cli=("--apb5",)),

    "ahb_lite": _spec("ahb_lite", "AHB-Lite", "amba", port_fmt="M{:02d}_AHB",
                      connect="ahb_lite", rtl="verif_ahb_lite_master", status="done",
                      cli=("--ahb", "--ahb_lite")),
    "ahb5_lite": _spec("ahb5_lite", "AHB5-Lite", "amba", port_fmt="M{:02d}_AHB",
                       connect="ahb5_lite", rtl="verif_ahb5_lite_master", status="smoke",
                       cli=("--ahb5",)),
    "ahb": _spec("ahb", "AHB (multi-master)", "amba", port_fmt="M{:02d}_AHB",
                 connect="ahb", rtl="verif_ahb_master", status="smoke",
                 cli=("--ahb_full",)),

    "axi4lite": _spec("axi4lite", "AXI4-Lite", "amba", port_fmt="S{:02d}_AXI",
                      connect="axi4lite", rtl="verif_axi_lite_master", status="done",
                      cli=("--axi", "--axi4lite")),
    "axi3full": _spec("axi3full", "AXI3 full", "amba", port_fmt="S{:02d}_AXI",
                      connect="axi3full", rtl="verif_axi_full_master", status="smoke",
                      cli=("--axi3",)),
    "axi4full": _spec("axi4full", "AXI4 full", "amba", port_fmt="S{:02d}_AXI",
                      connect="axi4full", rtl="verif_axi_full_master", status="smoke",
                      cli=("--axi4",)),
    "axi5full": _spec("axi5full", "AXI5 full", "amba", port_fmt="S{:02d}_AXI",
                      connect="axi5full", rtl="verif_axi_full_master", status="smoke",
                      cli=("--axi5",)),
    "axistream": _spec("axistream", "AXI4-Stream", "amba", port_fmt="S{:02d}_AXIS",
                       connect="axistream", rtl="verif_axistream_master", status="planned",
                       cli=("--axistream", "--axis"),
                       notes="Stream port — not memory-mapped"),

    "ace": _spec("ace", "ACE (coherent)", "amba", port_fmt="S{:02d}_ACE",
                 connect="ace", rtl="verif_ace_master", status="manifest_only",
                 cli=("--ace",), notes="Coherency snoop — chip-specific"),
    "ace_lite": _spec("ace_lite", "ACE-Lite", "amba", port_fmt="S{:02d}_ACELITE",
                      connect="ace_lite", rtl="verif_ace_lite_master", status="manifest_only",
                      cli=("--ace_lite",)),
    "chi": _spec("chi", "CHI (AMBA 5 coherent)", "amba", port_fmt="N{:02d}_CHI",
                 connect="chi", rtl="verif_chi_master", status="manifest_only",
                 cli=("--chi",), notes="Packet protocol — needs NoC/ICN spec"),
    "asb": _spec("asb", "ASB (legacy)", "amba", port_fmt="S{:02d}_ASB",
                 connect="asb", rtl="verif_asb_master", status="manifest_only",
                 cli=("--asb",), notes="AMBA2 legacy — rarely used"),

    "niu": _spec("niu", "NoC NIU (vendor)", "noc",
                 port_fmt="N{:02d}_NIU", connect="niu", rtl="verif_niu_master",
                 status="manifest_only", cli=("--niu",),
                 notes="Network Interface Unit — not ARM standard; needs vendor RTL/spec"),
}
# fmt: on

# Backward-compatible manifest names from early integration
LEGACY_BUS_ALIASES: dict[str, str] = {
    "apb": "apb3",
    "ahb": "ahb_lite",
    "axi": "axi4lite",
}

LAYOUT_BUS_KEYS: frozenset[str] = frozenset(
    k for k, s in BUS_TYPES.items() if k not in ("none",)
)

CLI_FLAG_TO_BUS: dict[str, str] = {}
for _key, _spec in BUS_TYPES.items():
    for _flag in _spec.cli_flags:
        CLI_FLAG_TO_BUS[_flag] = _key


def normalize_bus_type(name: str) -> str:
    n = name.strip().lower()
    return LEGACY_BUS_ALIASES.get(n, n)


def validate_bus_type(name: str) -> str:
    n = normalize_bus_type(name)
    if n not in BUS_TYPES:
        known = ", ".join(sorted(LAYOUT_BUS_KEYS))
        raise ValueError(f"unknown bus_type '{name}' (known: {known})")
    return n


def bus_port_for(cpu_id: int, bus_type: str) -> str:
    key = validate_bus_type(bus_type)
    spec = BUS_TYPES[key]
    if spec.port_fmt:
        return spec.port_fmt.format(cpu_id)
    return ""


def parse_layout_segment_types(spec: str) -> list[tuple[str, int]]:
    """Parse axi4lite:10,apb3:2 → [(canonical_key, count), ...]."""
    spec = spec.strip()
    if not spec:
        return []
    out: list[tuple[str, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"invalid BUS_LAYOUT segment: {part!r} (expected type:count)")
        raw_bt, cnt_s = part.split(":", 1)
        bt = validate_bus_type(raw_bt.strip())
        cnt = int(cnt_s.strip(), 0)
        if cnt < 0:
            raise ValueError(f"negative bus count in BUS_LAYOUT: {part!r}")
        out.append((bt, cnt))
    return out


def all_cli_flags() -> tuple[str, ...]:
    return tuple(sorted(CLI_FLAG_TO_BUS.keys(), key=len, reverse=True))


def iter_implemented_buses() -> Iterable[BusTypeSpec]:
    for spec in BUS_TYPES.values():
        if spec.rtl_status in ("done", "smoke"):
            yield spec


# CONNECT_SLVxx_<TAG> suffix and `CONNECT_*` macro in verif_amba_connect_macros.vh
CONNECT_SLV_TAGS: dict[str, tuple[str, str]] = {
    "apb2": ("APB2", "CONNECT_APB2"),
    "apb3": ("APB3", "CONNECT_APB3"),
    "apb4": ("APB4", "CONNECT_APB4"),
    "apb5": ("APB5", "CONNECT_APB5"),
    "ahb_lite": ("AHB_LITE", "CONNECT_AHB_LITE"),
    "ahb5_lite": ("AHB5_LITE", "CONNECT_AHB5_LITE"),
    "ahb": ("AHB", "CONNECT_AHB"),
    "axi4lite": ("AXI4LITE", "CONNECT_AXI_LITE"),
    "axi3full": ("AXI3FULL", "CONNECT_AXI3FULL"),
    "axi4full": ("AXI4FULL", "CONNECT_AXI4FULL"),
    "axi5full": ("AXI5FULL", "CONNECT_AXI5FULL"),
}


def connect_slv_tag(bus_type: str) -> str | None:
    key = normalize_bus_type(bus_type)
    return CONNECT_SLV_TAGS.get(key, (None, None))[0]


def connect_invoke_macro(bus_type: str) -> str | None:
    key = normalize_bus_type(bus_type)
    return CONNECT_SLV_TAGS.get(key, (None, None))[1]


def bus_supports_read_outstanding(bus_type: str) -> bool:
    return normalize_bus_type(bus_type) in BUS_READ_OUTSTANDING_TYPES


def bus_supports_write_outstanding(bus_type: str) -> bool:
    return normalize_bus_type(bus_type) in BUS_WRITE_OUTSTANDING_TYPES