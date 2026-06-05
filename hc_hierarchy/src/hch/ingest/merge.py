"""Merge ModuleRecord batches (same module_name from multiple files)."""

from __future__ import annotations

import json
from typing import Dict

from pathlib import Path

from hch.ingest.parse_tags import instance_edge_key
from hch.schema import ModuleRecord


def _prefer_module_file_path(module_name: str, prev_path: str, new_path: str) -> str:
    """Pick the RTL file that actually defines ``module_name``."""
    if not new_path:
        return prev_path
    if not prev_path:
        return new_path
    prev_stem = Path(prev_path).stem
    new_stem = Path(new_path).stem
    if prev_stem == module_name and new_stem != module_name:
        return prev_path
    if new_stem == module_name and prev_stem != module_name:
        return new_path
    return prev_path if len(prev_path) <= len(new_path) else new_path


def merge_module_records(
    acc: Dict[str, ModuleRecord],
    batch: Dict[str, ModuleRecord],
) -> None:
    for name, rec in batch.items():
        if name not in acc:
            acc[name] = rec
            continue
        prev = acc[name]
        if rec.is_blackbox and not prev.is_blackbox:
            continue
        if prev.is_blackbox and not rec.is_blackbox:
            acc[name] = rec
            prev = acc[name]
        if rec.file_path and rec.file_path != prev.file_path:
            paths = getattr(prev, "_definition_paths", None)
            if paths is None:
                paths = [prev.file_path] if prev.file_path else []
                prev._definition_paths = paths  # type: ignore[attr-defined]
            if rec.file_path not in paths:
                paths.append(rec.file_path)
            prev.parameters["_definition_paths"] = json.dumps(paths)
        if rec.file_path and not rec.is_blackbox:
            prev.file_path = _prefer_module_file_path(
                name, prev.file_path or "", rec.file_path
            )
        if len(rec.ports) > len(prev.ports):
            prev.ports = rec.ports
        if rec.parameters and not prev.parameters:
            prev.parameters = dict(rec.parameters)
        seen = {instance_edge_key(e) for e in prev.instances}
        for e in rec.instances:
            key = instance_edge_key(e)
            if key not in seen:
                prev.instances.append(e)
                seen.add(key)
        seen_bind = {(b.inst_name, b.child_module, b.target_module) for b in prev.binds}
        for b in rec.binds:
            bk = (b.inst_name, b.child_module, b.target_module)
            if bk not in seen_bind:
                prev.binds.append(b)
                seen_bind.add(bk)