"""
Hierarchy integration (migrated from regexVerilogAST elaboration.py).
Builds integrated module trees from per-file parse JSON.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from rvast.schema import Instance


class HierarchyElaborator:
    def __init__(
        self,
        work_dir: str,
        top_module: Optional[str] = None,
        ext: str = ".json",
    ):
        self.hierarchy_data = self._load_part_files(work_dir, ext)
        self.top_module = top_module
        self.integrated_hierarchy: Dict[str, Any] = {}

    def _load_part_files(self, work_dir: str, ext: str) -> Dict[str, Any]:
        hierarchy: Dict[str, Any] = {}
        for root, _, files in os.walk(work_dir):
            for filename in files:
                if not filename.endswith(ext):
                    continue
                filepath = os.path.join(root, filename)
                with open(filepath, encoding="utf-8") as f:
                    jdata = json.load(f)
                module_data = jdata.get("instances", {})
                for mod in module_data:
                    if isinstance(module_data[mod], dict):
                        module_data[mod]["filepath"] = jdata.get("filepath", filepath)
                hierarchy.update(module_data)
        return hierarchy

    def integrate_modules(self) -> Dict[str, Any]:
        top_modules: List[str] = []
        if self.top_module and self.top_module in self.hierarchy_data:
            top_modules.append(self.top_module)
        else:
            top_modules.extend(self.find_other_top_modules().keys())

        integrated: Dict[str, Any] = {}
        for module in top_modules:
            if module not in self.hierarchy_data:
                continue
            module_data = self.hierarchy_data[module]
            integrated[module] = {
                "instances": {},
                "filepath": module_data.get("filepath", ""),
                "module_ports": copy.deepcopy(module_data.get("ports", {})),
            }
            self._update_module(integrated[module], module_data, module)

        self.integrated_hierarchy = integrated
        return integrated

    def find_other_top_modules(self) -> Dict[str, Any]:
        instantiated: Set[str] = set()
        for v in self.hierarchy_data.values():
            for inst in v.get("instances", {}).values():
                if isinstance(inst, dict) and "module" in inst:
                    instantiated.add(inst["module"])

        toplist = set(self.hierarchy_data) - instantiated
        return {m: {} for m in toplist}

    @staticmethod
    def _extract_module_ports(data: Dict[str, Any]) -> Dict[str, Any]:
        if "module_ports" in data:
            return copy.deepcopy(data["module_ports"])
        ports = data.get("ports") or {}
        if isinstance(ports, dict) and ports:
            sample = next(iter(ports.values()))
            if isinstance(sample, dict) and "direction" in sample:
                return copy.deepcopy(ports)
        return {}

    def _update_module(
        self,
        module: Dict[str, Any],
        module_data: Dict[str, Any],
        module_name: str,
    ) -> None:
        module["module_ports"] = self._extract_module_ports(module_data)
        module["filepath"] = module_data.get("filepath", module.get("filepath", ""))

        for instance_name, instance in module_data.get("instances", {}).items():
            if not isinstance(instance, dict):
                continue
            child_mod = instance.get("module")
            if not child_mod or child_mod == "module":
                continue

            merged = copy.deepcopy(instance)
            merged["module"] = child_mod
            merged["filepath"] = (
                instance.get("file_path")
                or instance.get("filepath")
                or module_data.get("filepath", "")
            )

            if child_mod in self.hierarchy_data:
                child_data = self.hierarchy_data[child_mod]
                merged["module_ports"] = copy.deepcopy(child_data.get("ports", {}))
                merged["instances"] = copy.deepcopy(child_data.get("instances", {}))
                merged["filepath"] = child_data.get("filepath") or merged["filepath"]
                module["instances"][instance_name] = merged
                if merged.get("instances") and child_mod in self.hierarchy_data:
                    self._update_module(
                        merged,
                        self.hierarchy_data[child_mod],
                        child_mod,
                    )
            else:
                module["instances"][instance_name] = merged


def flatten_integrated_hierarchy(
    integrated: Dict[str, Any],
    top_name: Optional[str] = None,
) -> List[Instance]:
    """
    Walk integrated hierarchy and emit flat Instance rows for DQL.
    """
    instances: List[Instance] = []

    def port_names(mod_data: Dict[str, Any]) -> List[str]:
        raw = mod_data.get("module_ports")
        if raw is None:
            raw = mod_data.get("ports") or {}
        if isinstance(raw, dict):
            return list(raw.keys())
        return list(raw) if isinstance(raw, list) else []

    def walk(
        prefix: str,
        node: Dict[str, Any],
        module_type: str,
        filepath: str,
        depth: int,
        parent: Optional[str],
    ) -> None:
        name = prefix
        instances.append(
            Instance(
                name=name,
                module=module_type,
                file=filepath,
                ports=port_names(node),
                depth=depth,
                parent=parent,
            )
        )
        for inst_name, inst_data in (node.get("instances") or {}).items():
            if not isinstance(inst_data, dict):
                continue
            child_path = f"{prefix}.{inst_name}" if prefix else inst_name
            child_mod = inst_data.get("module") or inst_name
            if child_mod == "module":
                child_mod = inst_name
            child_file = inst_data.get("filepath") or inst_data.get("file_path") or filepath
            walk(child_path, inst_data, child_mod, child_file, depth + 1, prefix)

    for top, top_data in integrated.items():
        if top_name and top != top_name:
            continue
        walk(top, top_data, top, top_data.get("filepath", ""), 0, None)

    return instances


def _normalize_port_list(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, dict):
        return list(raw.keys())
    if isinstance(raw, (list, tuple)):
        return [str(p) for p in raw]
    return []


def propagator_rows_to_instances(rows: List[Dict[str, Any]]) -> List[Instance]:
    """Convert ParameterPropagator output to Instance list."""
    out: List[Instance] = []
    for r in rows:
        name = r.get("name", "")
        depth = name.count(".") if name else 0
        parent = ".".join(name.split(".")[:-1]) if "." in name else None
        ports = _normalize_port_list(
            r.get("ports") or r.get("port_list") or r.get("module_ports")
        )
        out.append(
            Instance(
                name=name,
                module=r.get("module", ""),
                file=r.get("file") or r.get("filepath", ""),
                ports=ports,
                parameters=dict(r.get("parameters") or {}),
                depth=depth,
                parent=parent or None,
            )
        )
    return out