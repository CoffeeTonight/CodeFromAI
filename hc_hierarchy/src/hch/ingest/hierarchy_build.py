"""
Build flat materialized paths from ModuleRecord graph (structural elaboration).

Generate for-loops with literal bounds are unrolled in Tier P extract
(``generate_path`` segments like ``gen_loop[0]``).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from hch.ingest.bind_attach import child_path_for_bind
from hch.ingest.flatten_tags import apply_edge_tags_to_flat
from hch.ingest.instance_resolve import resolve_instance_module_ref
from hch.ingest.multi_def import definition_paths_for_record
from hch.ingest.port_array_expand import materialized_port_names
from hch.schema import FlatInstance, InstanceEdge, ModuleRecord

MAX_FLATTEN_VISITS = 50_000
_flatten_cycle_detected = False
_flatten_warnings: List[str] = []


def flatten_cycle_detected() -> bool:
    return _flatten_cycle_detected


def get_flatten_warnings() -> List[str]:
    return list(_flatten_warnings)


def _add_flatten_warning(msg: str) -> None:
    if msg and msg not in _flatten_warnings:
        _flatten_warnings.append(msg)


def _reset_flatten_state() -> None:
    global _flatten_cycle_detected, _flatten_warnings
    _flatten_cycle_detected = False
    _flatten_warnings.clear()


def _path_hierarchy_depth_count(sources: Sequence[str]) -> int:
    from pathlib import Path

    from hch.ingest.path_hierarchy import instance_segments

    n = 0
    for src in sources:
        if len(instance_segments(src)) >= 2 and "soc_top" in Path(src).parts:
            n += 1
    return n


def elaborate_flat_with_sources(
    modules: Union[Mapping[str, ModuleRecord], List[ModuleRecord]],
    sources: Optional[Sequence[str]] = None,
    top_module: Optional[str] = None,
    top_modules: Optional[Sequence[str]] = None,
    *,
    path_depth_threshold: int = 10,
    path_hierarchy_mode: str = "auto",
) -> tuple[List[FlatInstance], str, str]:
    """
    Flatten module graph. When RTL uses soc_top/u_* directory layout (synthetic
    deep corpus), materialize paths from file paths — merged module names cannot
    hold a global instance graph without cycles.
    """
    if isinstance(modules, dict):
        mod_map: Dict[str, ModuleRecord] = dict(modules)
    else:
        mod_map = {m.module_name: m for m in modules}

    use_path = path_hierarchy_mode == "on"
    if path_hierarchy_mode == "auto":
        use_path = bool(
            sources
            and top_module
            and _path_hierarchy_depth_count(sources) >= path_depth_threshold
        )
    if use_path and sources and top_module:
        from hch.ingest.path_hierarchy import flat_instances_from_paths

        return flat_instances_from_paths(sources, mod_map, top_module), "path", "1"

    return (
        elaborate_flat(mod_map, top_module=top_module, top_modules=top_modules),
        "ast",
        "0",
    )


def find_top_modules(modules: Dict[str, ModuleRecord]) -> List[str]:
    instantiated: Set[str] = set()
    for rec in modules.values():
        for edge in rec.instances:
            instantiated.add(edge.child_module)
    all_mods = set(modules.keys())
    tops = sorted(all_mods - instantiated)
    return tops if tops else sorted(all_mods)


def elaborate_flat(
    modules: Union[Mapping[str, ModuleRecord], List[ModuleRecord]],
    top_module: Optional[str] = None,
    top_modules: Optional[Sequence[str]] = None,
    *,
    _visited: Optional[Set[str]] = None,
) -> List[FlatInstance]:
    if isinstance(modules, dict):
        mod_map = dict(modules)
    else:
        mod_map = {m.module_name: m for m in modules}
    if top_modules:
        tops = [t for t in top_modules if t in mod_map]
    elif top_module and top_module in mod_map:
        tops = [top_module]
    else:
        tops = find_top_modules(mod_map)
    _reset_flatten_state()
    out: List[FlatInstance] = []
    cycle_state = _visited if _visited is not None else set()
    mod_stack: Set[str] = set()
    visit_count = 0
    mod_paths: Dict[str, List[str]] = {}
    for rec in mod_map.values():
        for p in definition_paths_for_record(rec):
            mod_paths.setdefault(rec.module_name, [])
            if p not in mod_paths[rec.module_name]:
                mod_paths[rec.module_name].append(p)
    sibling_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    def walk(
        path: str,
        mod_name: str,
        depth: int,
        parent: Optional[str],
    ) -> None:
        global _flatten_cycle_detected
        nonlocal visit_count
        visit_count += 1
        if visit_count > MAX_FLATTEN_VISITS:
            _flatten_cycle_detected = True
            _add_flatten_warning(
                f"visit_cap_exceeded:{MAX_FLATTEN_VISITS} at {path or mod_name}"
            )
            return
        if mod_name in mod_stack:
            _flatten_cycle_detected = True
            _add_flatten_warning(f"module_stack_cycle:{mod_name} at {path or mod_name}")
            return
        visit_key = f"{path}::{mod_name}"
        if visit_key in cycle_state:
            _flatten_cycle_detected = True
            _add_flatten_warning(f"path_revisit_cycle:{visit_key}")
            return
        cycle_state.add(visit_key)
        mod_stack.add(mod_name)
        rec = mod_map.get(mod_name)
        if not rec:
            _add_flatten_warning(f"unresolved_module:{mod_name} at {path or mod_name}")
            out.append(
                FlatInstance(
                    full_path=path,
                    name=path.split(".")[-1] if path else mod_name,
                    module=mod_name,
                    file="",
                    ports=[],
                    depth=depth,
                    parent_path=parent,
                    child_kind="unresolved",
                    is_unresolved=True,
                )
            )
            return

        ports = materialized_port_names(rec.ports)
        out.append(
            FlatInstance(
                full_path=path,
                name=path.split(".")[-1] if "." in path else path,
                module=mod_name,
                file=rec.file_path,
                ports=ports,
                depth=depth,
                parent_path=parent,
                module_ref=resolve_instance_module_ref(
                    mod_name,
                    edge_file=rec.file_path,
                    parent_path=parent,
                    mod_paths_by_name=mod_paths,
                ),
            )
        )

        try:
            for edge in rec.instances:
                if getattr(edge, "unreachable", False):
                    continue
                if edge.via_bind and edge.bind_target_hier:
                    child_path = child_path_for_bind(
                        path,
                        mod_name,
                        edge.bind_target_hier,
                        edge.inst_name,
                    )
                    inst_seg = child_path.split(".")[-1] if child_path else edge.inst_name
                else:
                    inst_seg = edge.inst_name
                    if edge.generate_path:
                        inst_seg = f"{edge.generate_path}.{inst_seg}"
                    child_path = f"{path}.{inst_seg}" if path else inst_seg
                child_rec = mod_map.get(edge.child_module)
                if edge.child_kind:
                    child_kind = edge.child_kind
                elif edge.child_type == "primitive":
                    child_kind = "primitive"
                elif child_rec:
                    child_kind = child_rec.module_kind or "module"
                else:
                    child_kind = "unresolved"
                sib_key = (path or "", edge.child_module)
                sib_idx = sibling_counts[sib_key]
                sibling_counts[sib_key] += 1
                child_mref = resolve_instance_module_ref(
                    edge.child_module,
                    edge_file=edge.file_path,
                    parent_module_file=rec.file_path,
                    parent_path=path,
                    sibling_index=sib_idx,
                    mod_paths_by_name=mod_paths,
                )
                if not child_rec:
                    out.append(
                        FlatInstance(
                            full_path=child_path,
                            name=edge.inst_name,
                            module=edge.child_module,
                            file=edge.file_path,
                            ports=[],
                            depth=depth + 1,
                            parent_path=path,
                            param_overrides=dict(edge.param_overrides),
                            child_kind="unresolved",
                            is_unresolved=True,
                            in_generate=edge.in_generate,
                            via_bind=edge.via_bind,
                            generate_path=edge.generate_path or "",
                            generate_branch=edge.generate_branch or "",
                            module_ref=child_mref,
                        )
                    )
                    continue
                mark = len(out)
                walk(child_path, edge.child_module, depth + 1, path)
                for row in out[mark:]:
                    if row.full_path == child_path:
                        row.param_overrides = dict(edge.param_overrides)
                        row.child_kind = child_kind
                        row.module_ref = child_mref
                        apply_edge_tags_to_flat(row, edge)
                        if child_kind == "unresolved":
                            row.is_unresolved = True
                        break
        finally:
            mod_stack.discard(mod_name)

    for top in tops:
        walk(top, top, 0, None)

    return out