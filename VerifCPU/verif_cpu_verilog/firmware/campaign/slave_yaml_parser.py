"""Shared slave-row YAML parsing for campaign generators (DPI bind vs trace meta)."""

from __future__ import annotations

import sys
from typing import Any, Callable

SLAVE_META_TRACE_FIELDS = frozenset({"_trace", "_latency_trace"})

SLAVE_DPI_PARAM_KEYS = frozenset({
    "name",
    "cpu_id",
    "tap_port",
    "bus_type",
    "bus_port",
    "addr_base",
    "addr_size",
    "role",
    "enabled",
    "targets",
    "phase_c",
})


def warn_slave_meta_fields(
    ent: dict[str, Any],
    *,
    label: str = "slave",
    warn: Callable[[str], None] | None = None,
) -> list[str]:
    """Emit warnings for tolerated trace meta fields; return warning strings."""
    out: list[str] = []

    def _default_warn(msg: str) -> None:
        out.append(msg)
        print(f"[gen] WARN: {msg}", file=sys.stderr)

    emit = warn or _default_warn
    for key in sorted(SLAVE_META_TRACE_FIELDS):
        if key in ent:
            emit(f"{label}: ignoring meta field {key!r} (not in DPI param list)")
    return out


def slave_dpi_bind_fields(ent: dict[str, Any]) -> dict[str, Any]:
    """Return only fields that may feed RTL/DPI generator parameter lists."""
    return {k: v for k, v in ent.items() if k in SLAVE_DPI_PARAM_KEYS}


def require_slave_name_cpu_id(
    full: dict[str, Any],
    dpi: dict[str, Any],
) -> tuple[str, int]:
    name = dpi.get("name") or full.get("name")
    cpu_raw = dpi.get("cpu_id") if dpi.get("cpu_id") is not None else full.get("cpu_id")
    if not name or cpu_raw is None:
        raise ValueError(f"slave row missing name or cpu_id: {full!r}")
    return str(name), int(cpu_raw)


def parse_slave_yaml_ent(
    ent: dict[str, Any],
    *,
    label: str = "slave",
    warn: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Parse one slave row: (full_row, dpi_bind_fields, warnings)."""
    warnings = warn_slave_meta_fields(ent, label=label, warn=warn)
    return dict(ent), slave_dpi_bind_fields(ent), warnings
