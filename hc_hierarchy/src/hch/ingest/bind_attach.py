"""Bind instance path attachment under hierarchical targets."""

from __future__ import annotations


def bind_anchor_relative(hier_path: str, parent_module: str) -> str:
    """
    Strip leading target module from ``bind sub.u_sub`` style paths.

    Returns instance path under *parent_module* (e.g. ``u_sub``).
    """
    if not hier_path:
        return ""
    parts = hier_path.split(".")
    if parts and parts[0] == parent_module:
        parts = parts[1:]
    return ".".join(parts)


def child_path_for_bind(
    parent_flat_path: str,
    parent_module: str,
    bind_target_hier: str,
    inst_name: str,
) -> str:
    """Build flat path for a bind instance under an anchor instance."""
    anchor = bind_anchor_relative(bind_target_hier, parent_module)
    if anchor:
        seg = f"{anchor}.{inst_name}"
    else:
        seg = inst_name
    return f"{parent_flat_path}.{seg}" if parent_flat_path else seg