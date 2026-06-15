"""Lazy processing: endpoint scope paths and elab/connect filtering."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from scan_inst.connect_request import ConnectivityCheck, ConnectivityRequest


def lazy_processing_enabled() -> bool:
    """Default on; set ``SCAN_INST_LAZY=0`` to disable scoped elab / light index."""
    import os

    raw = os.environ.get("SCAN_INST_LAZY", "").strip().lower()
    return raw not in ("0", "off", "false", "no", "disable", "disabled")


def endpoint_specs_from_checks(checks: Sequence[ConnectivityCheck]) -> List[str]:
    out: List[str] = []
    for chk in checks:
        if chk.endpoint_a:
            out.append(chk.endpoint_a)
        if chk.endpoint_b:
            out.append(chk.endpoint_b)
    return out


def endpoint_specs_from_request(
    request: Optional[ConnectivityRequest],
    *,
    pair: Optional[tuple[str, str]] = None,
) -> List[str]:
    specs: List[str] = []
    if request is not None:
        specs.extend(endpoint_specs_from_checks(request.checks))
    if pair is not None:
        a, b = pair
        if a:
            specs.append(a)
        if b:
            specs.append(b)
    return specs


def hierarchy_prefixes(specs: Iterable[str]) -> Set[str]:
    """All dotted prefixes for endpoint specs (hierarchy path candidates)."""
    out: Set[str] = set()
    for raw in specs:
        spec = str(raw).strip()
        if not spec:
            continue
        parts = spec.split(".")
        for i in range(1, len(parts) + 1):
            out.add(".".join(parts[:i]))
    return out


def elab_scope_paths(
    endpoint_specs: Iterable[str],
    *,
    top: str = "",
) -> Set[str]:
    """
    Instance paths to elaborate: prefixes of every endpoint spec.

    When *top* is set, ensure it is included.
    """
    scope = hierarchy_prefixes(endpoint_specs)
    if top:
        scope.add(top)
        filtered = {p for p in scope if p == top or p.startswith(top + ".")}
        if filtered:
            scope = filtered
    return scope


def child_path_in_scope(child_path: str, scope_paths: Optional[Set[str]]) -> bool:
    if not scope_paths:
        return True
    for sp in scope_paths:
        if sp == child_path or sp.startswith(child_path + "."):
            return True
    return False