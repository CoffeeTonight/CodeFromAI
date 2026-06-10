"""Lightweight text-only ingest (no pyslang) for shallow conditional-depth files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from hch.ingest.parse_depth import modules_defined_in_file
from hch.ingest.text_instance_fallback import (
    apply_ifdef_filter,
    extract_module_body,
    scan_hierarchy_instances,
)
from hch.schema import InstanceEdge, ModuleRecord


def ingest_sources_text_skim(
    filenames: Sequence[str],
    defines: Optional[Mapping[str, str]] = None,
) -> Dict[str, ModuleRecord]:
    """Build ModuleRecord graph from RTL text (instances only, no ports/generate)."""
    merged: Dict[str, ModuleRecord] = {}
    for raw_path in filenames:
        path = str(Path(raw_path).resolve())
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        filtered = apply_ifdef_filter(text, defines)
        for mod_name in modules_defined_in_file(path, defines):
            body = extract_module_body(filtered, mod_name)
            if not body:
                continue
            edges: List[InstanceEdge] = []
            seen: set[tuple[str, str]] = set()
            for child_mod, inst_name in scan_hierarchy_instances(body):
                key = (inst_name, child_mod)
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    InstanceEdge(
                        parent_module=mod_name,
                        inst_name=inst_name,
                        child_module=child_mod,
                        file_path=path,
                        child_kind="text_skim",
                    )
                )
            merged[mod_name] = ModuleRecord(
                module_name=mod_name,
                file_path=path,
                instances=edges,
                parse_tier="skim",
            )
    return merged