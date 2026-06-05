"""Detect unresolved child modules after structural ingest."""

from __future__ import annotations

from typing import Dict, List, Mapping, Set

from hch.schema import ModuleRecord


def collect_unresolved_modules(
    modules: Mapping[str, ModuleRecord],
) -> List[str]:
    """Child module names referenced by instances but not defined in *modules*."""
    defined = set(modules.keys())
    refs: Set[str] = set()
    for rec in modules.values():
        for edge in rec.instances:
            if edge.child_module:
                refs.add(edge.child_module)
    return sorted(refs - defined)


def ensure_unresolved_module_stubs(modules: Dict[str, ModuleRecord]) -> int:
    """
    Insert placeholder ``module_kind=unresolved`` records for missing children.

    Required so flat rows referencing undefined modules can be stored in SQLite.
    Returns number of stubs added.
    """
    added = 0
    for rec in list(modules.values()):
        for edge in rec.instances:
            cm = edge.child_module
            if not cm or cm in modules:
                continue
            modules[cm] = ModuleRecord(
                module_name=cm,
                file_path=edge.file_path,
                module_kind="unresolved",
            )
            added += 1
    return added