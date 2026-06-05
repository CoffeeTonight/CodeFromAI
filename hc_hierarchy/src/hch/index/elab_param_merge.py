"""Merge Tier E elaborated parameters with Tier P structural overrides."""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional

from hch.engine.elab_result import ElabInstance
from hch.schema import FlatInstance, ModuleRecord


def tier_p_params_for_child(
    mod_map: Mapping[str, ModuleRecord],
    parent_module: str,
    inst_name: str,
    child_module: str,
) -> Dict[str, str]:
    """Lookup ``#()`` overrides from the parent's structural instance edges."""
    rec = mod_map.get(parent_module)
    if not rec:
        return {}
    leaf = inst_name.split(".")[-1] if inst_name else inst_name
    for edge in rec.instances:
        if edge.child_module != child_module:
            continue
        ename = edge.inst_name
        if ename == inst_name or ename == leaf or inst_name.endswith(f".{ename}"):
            return dict(edge.param_overrides)
    return {}


def merge_elab_and_tier_p_params(
    elab: ElabInstance,
    mod_map: Mapping[str, ModuleRecord],
    path_to_module: Mapping[str, str],
    *,
    top_module: Optional[str] = None,
) -> Dict[str, str]:
    """
    Combine elaborated resolved parameters with Tier P syntax overrides.

    Elaborated values win on key collision; Tier P fills gaps when elab omitted
    a parameter (partial elab / blackbox child).
    """
    merged = dict(elab.param_overrides)
    parent_path = elab.parent_path
    if parent_path:
        parent_mod = path_to_module.get(parent_path, "")
        if parent_mod:
            tier_p = tier_p_params_for_child(
                mod_map, parent_mod, elab.inst_name, elab.module
            )
            for key, val in tier_p.items():
                merged.setdefault(key, val)
    elif top_module:
        tier_p = tier_p_params_for_child(
            mod_map, top_module, elab.inst_name, elab.module
        )
        for key, val in tier_p.items():
            merged.setdefault(key, val)
    return merged


def flat_instances_from_elab(
    elab_instances: List[ElabInstance],
    mod_map: Mapping[str, ModuleRecord],
    *,
    top_module: Optional[str] = None,
) -> List[FlatInstance]:
    """Build FlatInstance rows from elaborated instances with merged parameters."""
    path_to_module = {e.full_path: e.module for e in elab_instances}
    from hch.ingest.instance_resolve import resolve_instance_module_ref
    from hch.ingest.multi_def import definition_paths_for_record

    mod_paths: dict = {}
    for rec in mod_map.values():
        for p in definition_paths_for_record(rec):
            mod_paths.setdefault(rec.module_name, [])
            if p not in mod_paths[rec.module_name]:
                mod_paths[rec.module_name].append(p)
    flat: List[FlatInstance] = []
    for e in elab_instances:
        rec = mod_map.get(e.module)
        ports = [p.name for p in rec.ports if p.name] if rec else []
        fpath = rec.file_path if rec else ""
        child_kind = rec.module_kind if rec else "module"
        params = merge_elab_and_tier_p_params(
            e, mod_map, path_to_module, top_module=top_module
        )
        mref = resolve_instance_module_ref(
            e.module,
            edge_file=fpath,
            parent_path=e.parent_path,
            mod_paths_by_name=mod_paths,
        )
        flat.append(
            FlatInstance(
                full_path=e.full_path,
                name=e.inst_name,
                module=e.module,
                file=fpath,
                ports=ports,
                depth=e.depth,
                parent_path=e.parent_path,
                param_overrides=params,
                child_kind=child_kind,
                module_ref=mref,
            )
        )
    return flat