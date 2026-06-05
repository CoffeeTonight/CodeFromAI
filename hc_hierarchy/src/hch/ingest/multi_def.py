"""Multi-definition module helpers (same ``module_name``, several RTL files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from hch.schema import ModuleRecord


def module_ref(file_path: str, module_name: str) -> str:
    from hch.platform_paths import path_to_db

    fp = path_to_db(file_path) if file_path else ""
    return f"{fp}::{module_name}"


def definition_paths_for_record(
    rec: ModuleRecord,
    *,
    extra_paths: Optional[Sequence[str]] = None,
) -> List[str]:
    paths: List[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        if not raw:
            return
        from hch.platform_paths import path_to_db

        p = path_to_db(raw)
        if p not in seen:
            seen.add(p)
            paths.append(p)

    add(rec.file_path)
    raw = rec.parameters.get("_definition_paths")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    add(str(item))
        except (json.JSONDecodeError, TypeError):
            pass
    attr = getattr(rec, "_definition_paths", None)
    if attr:
        for item in attr:
            add(str(item))
    for item in extra_paths or ():
        add(str(item))
    return paths


def expand_multi_def_module_records(
    modules: Iterable[ModuleRecord],
    *,
    extra_paths_by_name: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[ModuleRecord]:
    """
    One :class:`ModuleRecord` per physical definition path for store/DQL ``module_ref``.

    The primary record keeps instances/ports; alias rows share ``module_name`` only.
    """
    out: List[ModuleRecord] = []
    extras = extra_paths_by_name or {}
    for rec in modules:
        paths = definition_paths_for_record(rec, extra_paths=extras.get(rec.module_name))
        if not paths:
            out.append(rec)
            continue
        primary = str(Path(rec.file_path).resolve()) if rec.file_path else paths[0]
        for fp in paths:
            if fp == primary:
                out.append(rec)
                continue
            params = {
                k: v
                for k, v in rec.parameters.items()
                if k != "_definition_paths"
            }
            params["primary_definition_file"] = primary
            out.append(
                ModuleRecord(
                    module_name=rec.module_name,
                    file_path=fp,
                    ports=list(rec.ports),
                    parameters=params,
                    instances=[],
                    binds=[],
                    is_blackbox=rec.is_blackbox,
                    module_kind=rec.module_kind,
                )
            )
    return out