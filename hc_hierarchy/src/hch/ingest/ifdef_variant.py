"""Compare instance sets across preprocessor variants."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Set, Tuple

from hch.schema import ModuleRecord


def instance_set_under_top(
    modules: Mapping[str, ModuleRecord],
    top_module: str,
) -> Set[Tuple[str, str]]:
    """
    Structural edges under *top_module*: ``(inst_name, child_module)`` pairs.
    """
    if top_module not in modules:
        return set()
    return {
        (e.inst_name, e.child_module)
        for e in modules[top_module].instances
        if e.inst_name and e.child_module
    }


def compare_instance_sets(
    left: Iterable[Tuple[str, str]],
    right: Iterable[Tuple[str, str]],
) -> Dict[str, Set[Tuple[str, str]]]:
    a, b = set(left), set(right)
    return {
        "only_left": a - b,
        "only_right": b - a,
        "common": a & b,
    }