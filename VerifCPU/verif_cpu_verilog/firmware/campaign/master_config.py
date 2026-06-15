"""Shared master (SCPU0) superset configuration parsing."""

from __future__ import annotations

from typing import Any

NOOP_PHASE_C = "cpu_generic/noop.c"


def parse_targets(ent: dict, resolve_addr) -> list[dict]:
    out: list[dict] = []
    for t in ent.get("targets") or []:
        sym = t["sym"]
        out.append({
            "sym": sym,
            "addr": resolve_addr(sym),
            "expect": t["expect"] if isinstance(t["expect"], int) else int(t["expect"], 0),
            "icode": t["icode"],
        })
    return out


def load_master(raw: dict, *, num_scpu: int, resolve_addr) -> dict:
    """Build normalized master dict; enabled defaults to 1 when num_scpu==0 else 0."""
    ent: dict[str, Any] = dict(raw.get("master") or {})
    enabled_raw = ent.get("enabled")
    if enabled_raw is None:
        vcpu_enabled = 1 if num_scpu == 0 else 0
    else:
        vcpu_enabled = 1 if bool(enabled_raw) else 0

    targets = parse_targets(ent, resolve_addr)
    return {
        "mode": str(ent.get("mode", "superset")),
        "name": str(ent.get("name", "MSTR")),
        "vcpu_enabled": vcpu_enabled,
        "tap_port": int(ent.get("tap_port", 0)),
        "role": str(ent.get("role", "master")),
        "phase_c": str(ent.get("phase_c", NOOP_PHASE_C)),
        "bus_type": str(ent.get("bus_type", "task")),
        "bus_port": str(ent.get("bus_port", "") or ""),
        "pool_word": 0,
        "pool_index": 0,
        "target_count": len(targets),
        "targets": targets,
    }


def master_has_agent(master: dict) -> bool:
    return bool(master.get("vcpu_enabled") and master.get("targets"))


def pool_vcpu_regions(num_scpu: int, master: dict) -> int:
    """Word regions reserved for VCPU firmware (master + slaves)."""
    n = num_scpu
    if master.get("vcpu_enabled"):
        n = max(n, 1)
    return n