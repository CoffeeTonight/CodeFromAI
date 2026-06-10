"""Path-based IP blackbox: skip full parse, text-skim structural ingest."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from hch.ingest.filelist_preprocess import FilelistResult
from hch.ingest.hierarchy_build import find_top_modules
from hch.ingest.text_skim import ingest_sources_text_skim
from hch.schema import ModuleRecord


def resolve_blackbox_path_patterns(
    blackbox_paths: Sequence[str] = (),
) -> List[str]:
    """CLI ``--blackbox-path`` plus optional env ``HCH_BLACKBOX_PATH`` (comma-separated)."""
    patterns: List[str] = []
    env = os.environ.get("HCH_BLACKBOX_PATH", "").strip()
    if env:
        patterns.extend(p.strip() for p in env.split(",") if p.strip())
    for p in blackbox_paths:
        s = str(p).strip()
        if s and s not in patterns:
            patterns.append(s)
    return patterns


def source_path_matches(path: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return False
    norm = str(path).replace("\\", "/")
    return any(pat in norm for pat in patterns)


def partition_sources(
    sources: Sequence[str],
    patterns: Sequence[str],
) -> Tuple[List[str], List[str]]:
    if not patterns:
        return list(sources), []
    parse_out: List[str] = []
    kit_out: List[str] = []
    for src in sources:
        if source_path_matches(src, patterns):
            kit_out.append(src)
        else:
            parse_out.append(src)
    return parse_out, kit_out


def scan_kit_blackbox_modules(
    kit_sources: Sequence[str],
    defines: Optional[Mapping[str, str]] = None,
) -> Dict[str, ModuleRecord]:
    """
    Text-skim structural ingest for blackbox RTL (no pyslang).

    Modules keep instance edges for orphan-root flatten; callers that flatten from
    a non-blackbox primary top should stop at blackbox instance boundaries.
    """
    if not kit_sources:
        return {}
    skimmed = ingest_sources_text_skim(kit_sources, defines=defines)
    out: Dict[str, ModuleRecord] = {}
    for name, rec in skimmed.items():
        out[name] = replace(
            rec,
            is_blackbox=True,
            parse_tier="blackbox",
        )
    return out


def flatten_roots_with_blackbox(
    modules: Mapping[str, ModuleRecord],
    primary_top: Optional[str],
    tops: Optional[Sequence[str]],
    patterns: Sequence[str],
) -> Tuple[List[str], Optional[Set[str]]]:
    """
    Return ``(flatten_tops, blackbox_boundary_roots)`` for elaborate_flat*.

    Primary top stops at blackbox instance stubs; orphan blackbox tops flatten fully.
    """
    primary = (primary_top or "").strip()
    base = list(tops) if tops else ([primary] if primary else [])
    orphans = blackbox_orphan_flatten_roots(modules, primary, patterns)
    if orphans:
        base = list(dict.fromkeys([*base, *orphans]))
    boundary: Optional[Set[str]] = {primary} if primary and patterns else None
    return base, boundary


def reapply_kit_blackbox_overlay(
    modules: Dict[str, ModuleRecord],
    kit_mods: Mapping[str, ModuleRecord],
    kit_sources: Sequence[str],
    patterns: Sequence[str],
) -> int:
    """
    Force kit blackbox stubs after pyslang/incdir may have upgraded them to full.

    Returns number of module records replaced.
    """
    if not patterns or not kit_mods:
        return 0
    replaced = 0
    for name, kit_rec in kit_mods.items():
        modules[name] = kit_rec
        replaced += 1
    kit_paths = {str(Path(p).resolve()) for p in kit_sources}
    for name, rec in list(modules.items()):
        if name in kit_mods:
            continue
        fp = rec.file_path or ""
        if not fp:
            continue
        resolved = str(Path(fp).resolve())
        if resolved in kit_paths or source_path_matches(fp, patterns):
            modules[name] = replace(
                rec,
                is_blackbox=True,
                parse_tier="blackbox",
            )
            replaced += 1
    return replaced


def blackbox_orphan_flatten_roots(
    modules: Mapping[str, ModuleRecord],
    primary_top: Optional[str],
    patterns: Sequence[str],
) -> List[str]:
    """
    Uninstantiated module tops inside blackboxed sources — flatten as extra roots.

    Example: ``filelist.f`` uses ``hc_verify_top`` while ``top_module`` lives only
    under ``rtl/hfa/`` and is fully blackboxed.
    """
    if not patterns:
        return []
    bb_mods = {
        name: rec
        for name, rec in modules.items()
        if rec.file_path and source_path_matches(rec.file_path, patterns)
    }
    if not bb_mods:
        return []
    tops = find_top_modules(bb_mods)
    primary = (primary_top or "").strip()
    return [t for t in tops if t and t != primary]


def filter_filelist_for_parse(
    fl: FilelistResult,
    patterns: Sequence[str],
) -> Tuple[FilelistResult, List[str]]:
    """Return a copy of *fl* with kit paths removed from ``source_files``."""
    if not patterns:
        return fl, []
    kept: List[Path] = []
    kit: List[str] = []
    for sp in fl.source_files:
        resolved = str(sp.resolve())
        if source_path_matches(resolved, patterns):
            kit.append(resolved)
        else:
            kept.append(sp)
    return replace(fl, source_files=kept), kit


def kit_blackbox_meta(
    patterns: Sequence[str],
    kit_sources: Sequence[str],
    kit_modules: Dict[str, ModuleRecord],
) -> Dict[str, str]:
    if not patterns:
        return {}
    return {
        "kit_blackbox_patterns_json": json.dumps(list(patterns)),
        "kit_blackbox_sources_json": json.dumps(sorted(set(str(s) for s in kit_sources))),
        "kit_blackbox_source_count": str(len(kit_sources)),
        "kit_blackbox_module_count": str(len(kit_modules)),
    }


def kit_blackbox_source_paths(meta: Mapping[str, str]) -> Set[str]:
    raw = meta.get("kit_blackbox_sources_json", "").strip()
    if not raw:
        return set()
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if isinstance(loaded, list):
        return {str(p).strip() for p in loaded if str(p).strip()}
    return set()