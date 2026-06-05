"""Shared keys for instance dedup and parametric signatures."""

from __future__ import annotations

from typing import Dict, Tuple

from hch.schema import InstanceEdge


def param_signature(overrides: Dict[str, str]) -> str:
    if not overrides:
        return ""
    return "|".join(f"{k}={v}" for k, v in sorted(overrides.items()))


def instance_edge_key(edge: InstanceEdge) -> Tuple[str, str, str, str]:
    return (
        edge.inst_name,
        edge.child_module,
        param_signature(edge.param_overrides),
        edge.generate_path or "",
    )