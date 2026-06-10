"""
Infer structural instance edges from RTL directory layout (u_* path segments).

Synthetic deep RTL places each hierarchy node under soc_top/u_.../module.v without
body instantiations; Tier P AST extract alone yields a shallow tree. This pass
augments the module graph so elaborate_flat can reach full depth.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from hch.ingest.port_array_expand import materialized_port_names
from hch.schema import InstanceEdge, ModuleRecord

_MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_]\w*)", re.MULTILINE)
_name_cache: dict[tuple[str, float], str] = {}


def module_name_from_file(path: str | Path) -> str:
    p = Path(path)
    try:
        key = (str(p.resolve()), p.stat().st_mtime)
    except OSError:
        return ""
    hit = _name_cache.get(key)
    if hit is not None:
        return hit
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        _name_cache[key] = ""
        return ""
    m = _MODULE_RE.search(text)
    name = m.group(1) if m else ""
    _name_cache[key] = name
    return name


def instance_segments(path: str | Path) -> List[str]:
    return [p for p in Path(path).parts if p.startswith("u_")]


def _resolved(path: str | Path) -> str:
    return str(Path(path).resolve())


def build_file_module_index(sources: Sequence[str | Path]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for src in sources:
        key = _resolved(src)
        name = module_name_from_file(src)
        if name:
            out[key] = name
    return out


def augment_instance_edges_from_paths(
    modules: Mapping[str, ModuleRecord],
    sources: Sequence[str | Path],
    *,
    top_module: Optional[str] = None,
    soc_top_marker: str = "soc_top",
) -> int:
    """
    Add parent→child InstanceEdge entries derived from directory nesting.
    Returns number of edges added.
    """
    file_mod = build_file_module_index(sources)
    added = 0
    seen: Dict[str, Set[Tuple[str, str]]] = {
        name: {(e.inst_name, e.child_module) for e in rec.instances}
        for name, rec in modules.items()
    }

    for src in sources:
        segs = instance_segments(src)
        if len(segs) < 2:
            continue
        p = Path(src).resolve()
        parts = p.parts
        if soc_top_marker not in parts:
            continue

        child_inst = segs[-1]
        child_mod = file_mod.get(str(p)) or module_name_from_file(p)
        if not child_inst or not child_mod:
            continue

        parent_dir = p.parent.parent
        parent_mod = ""
        for pv in sorted(parent_dir.glob("*.v")):
            parent_mod = file_mod.get(str(pv.resolve())) or module_name_from_file(pv)
            if parent_mod:
                break
        if not parent_mod or parent_mod not in modules:
            continue

        key = (child_inst, child_mod)
        if key in seen[parent_mod]:
            continue
        modules[parent_mod].instances.append(
            InstanceEdge(
                parent_module=parent_mod,
                inst_name=child_inst,
                child_module=child_mod,
                file_path=str(p),
            )
        )
        seen[parent_mod].add(key)
        added += 1

    return added


def flat_instances_from_paths(
    sources: Sequence[str | Path],
    modules: Mapping[str, ModuleRecord],
    top_module: str,
    *,
    max_depth: Optional[int] = None,
    conditional_depth: Optional["ConditionalDepthPolicy"] = None,
    deepened_prefixes: Optional[Sequence[str]] = None,
) -> List:
    """Materialize one FlatInstance per RTL path node (fallback / supplement)."""
    from hch.schema import FlatInstance

    file_mod = build_file_module_index(sources)
    rows: List[FlatInstance] = []
    seen_paths: Set[str] = set()

    top_rec = modules.get(top_module)
    top_ports = materialized_port_names(top_rec.ports) if top_rec else []
    top_file = top_rec.file_path if top_rec else ""
    rows.append(
        FlatInstance(
            full_path=top_module,
            name=top_module,
            module=top_module,
            file=top_file,
            ports=top_ports,
            depth=0,
            parent_path=None,
        )
    )
    seen_paths.add(top_module)

    for src in sources:
        segs = instance_segments(src)
        if not segs:
            continue
        p = Path(src).resolve()
        mod = file_mod.get(str(p)) or module_name_from_file(p)
        if not mod:
            continue
        full = f"{top_module}.{'.'.join(segs)}"
        if full in seen_paths:
            continue
        rec = modules.get(mod)
        ports = materialized_port_names(rec.ports) if rec else []
        parent = top_module if len(segs) == 1 else f"{top_module}.{'.'.join(segs[:-1])}"
        inst_depth = len(segs)
        if max_depth is not None and inst_depth > max_depth:
            continue
        if conditional_depth is not None:
            from hch.ingest.parse_depth import (
                descendant_hops_for_node,
                path_has_deepened_prefix,
                path_matches_anchor,
            )

            full = f"{top_module}.{'.'.join(segs)}"
            file_path = str(p)
            if deepened_prefixes and path_has_deepened_prefix(full, deepened_prefixes):
                pass
            elif not path_matches_anchor(
                full, file_path, conditional_depth.anchor_patterns
            ):
                # shallow zone: keep only shallow_depth path segments below last anchor
                anchor_depth = 0
                for i in range(len(segs)):
                    prefix = f"{top_module}.{'.'.join(segs[: i + 1])}"
                    if path_matches_anchor(
                        prefix, file_path, conditional_depth.anchor_patterns
                    ):
                        anchor_depth = i + 1
                if len(segs) - anchor_depth > conditional_depth.shallow_depth:
                    continue
        rows.append(
            FlatInstance(
                full_path=full,
                name=segs[-1],
                module=mod,
                file=str(p),
                ports=ports,
                depth=inst_depth,
                parent_path=parent,
            )
        )
        seen_paths.add(full)

    return rows