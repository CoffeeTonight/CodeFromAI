"""Reduce slang compile sources to the module closure reachable from top(s)."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from hch.ingest.path_hierarchy import build_file_module_index, instance_segments, module_name_from_file
from hch.schema import InstanceEdge, ModuleRecord

__all__ = [
    "build_module_path_index",
    "prune_sources_for_elab",
    "resolve_module_source_path",
]

InstKey = Tuple[str, str]
ModulePathIndex = Dict[str, List[str]]


def _resolved(path: str | Path) -> str:
    return str(Path(path).resolve())


def build_module_path_index(sources: Sequence[str | Path]) -> ModulePathIndex:
    """Map module name → RTL paths (one pass over ``sources``)."""
    index: ModulePathIndex = {}
    use_stem = len(sources) > 64
    file_mod: Dict[str, str] = {}
    if not use_stem:
        file_mod = build_file_module_index(sources)

    for src in sources:
        p = _resolved(src)
        names: List[str] = []
        if use_stem:
            names.append(Path(p).stem)
        else:
            m = file_mod.get(p) or module_name_from_file(p)
            if m:
                names.append(m)
            if Path(p).stem not in names:
                names.append(Path(p).stem)
        for name in names:
            if not name:
                continue
            bucket = index.setdefault(name, [])
            if p not in bucket:
                bucket.append(p)
    return index


def _pick_best_path(
    hits: List[str],
    *,
    prefer_near: Optional[str | Path] = None,
) -> str:
    if len(hits) == 1:
        return hits[0]
    stem_hits = list(hits)
    if prefer_near:
        anchor = Path(prefer_near).resolve().parent
        near = [
            h
            for h in stem_hits
            if anchor == Path(h).resolve().parent
            or anchor in Path(h).resolve().parents
        ]
        if near:
            stem_hits = near
    stem_hits.sort(key=lambda h: (len(Path(h).parts), len(h)))
    return stem_hits[0]


def resolve_module_source_path(
    module_name: str,
    sources: Sequence[str | Path],
    *,
    prefer_near: Optional[str | Path] = None,
    module_index: Optional[ModulePathIndex] = None,
) -> Optional[str]:
    """Return the RTL file that defines ``module_name`` among ``sources``."""
    if module_index is not None:
        hits = module_index.get(module_name, [])
        if not hits:
            return None
        return _pick_best_path(hits, prefer_near=prefer_near)

    stem_hits: List[str] = []
    for src in sources:
        p = Path(src)
        if p.stem == module_name:
            stem_hits.append(_resolved(p))
        else:
            rp = _resolved(src)
            if module_name_from_file(rp) == module_name:
                stem_hits.append(rp)
    if not stem_hits:
        return None
    return _pick_best_path(stem_hits, prefer_near=prefer_near)


def _module_file(mod: ModuleRecord) -> Optional[str]:
    name = mod.module_name
    candidates: List[str] = []
    if mod.file_path:
        candidates.append(mod.file_path)
    paths_raw = mod.parameters.get("_definition_paths")
    if paths_raw:
        try:
            candidates.extend(json.loads(paths_raw))
        except (json.JSONDecodeError, TypeError):
            pass
    for raw in candidates:
        try:
            p = _resolved(raw)
        except OSError:
            continue
        if Path(p).stem == name:
            return p
    return None


def _build_inst_module_files(sources: Sequence[str | Path]) -> Dict[InstKey, str]:
    """Map (u_* instance segment, module name) → defining RTL path."""
    out: Dict[InstKey, str] = {}
    use_stem_only = len(sources) > 64
    file_mod: Dict[str, str] = {}
    if not use_stem_only:
        file_mod = build_file_module_index(sources)
    for src in sources:
        p = _resolved(src)
        segs = instance_segments(src)
        mod = (
            Path(p).stem
            if use_stem_only
            else (file_mod.get(p) or module_name_from_file(p))
        )
        if not mod:
            continue
        if segs:
            out[(segs[-1], mod)] = p
        out[(mod, mod)] = p
    return out


def _guess_inst_child_path(
    inst: str,
    child: str,
    sources: Sequence[str | Path],
) -> Optional[str]:
    """Resolve top-level ``u_*`` / ``soc_top/u_*/mod.v`` layout."""
    if not inst or not child or not sources:
        return None
    roots = {Path(s).resolve().parent for s in sources}
    for root in roots:
        for base in (root, root.parent, root / "soc_top", root.parent / "soc_top"):
            for trial in (
                base / inst / f"{child}.v",
                base / "soc_top" / inst / f"{child}.v",
                base / f"{inst}.v",
            ):
                if trial.is_file() and module_name_from_file(trial) == child:
                    return _resolved(trial)
    return None


def _edge_source_file(
    edge: InstanceEdge,
    inst_lookup: Mapping[InstKey, str],
    modules: Mapping[str, ModuleRecord],
    sources: Sequence[str | Path],
    *,
    module_index: Optional[ModulePathIndex] = None,
) -> Optional[str]:
    child = (edge.child_module or "").strip()
    inst = (edge.inst_name or "").strip()
    parent_fp = edge.file_path or None
    if child and sources:
        near = resolve_module_source_path(
            child,
            sources,
            prefer_near=parent_fp,
            module_index=module_index,
        )
        if near:
            return near
    if inst and child:
        hit = _guess_inst_child_path(inst, child, sources)
        if hit:
            return hit
        hit = inst_lookup.get((inst, child))
        if hit and (
            Path(hit).stem == child
            or module_name_from_file(hit) == child
        ):
            return hit
    if edge.file_path:
        fp = _resolved(edge.file_path)
        if Path(fp).stem == child or module_name_from_file(fp) == child:
            return fp
    rec = modules.get(child)
    if rec:
        return _module_file(rec)
    return None


def prune_sources_for_elab(
    modules: Mapping[str, ModuleRecord],
    top_modules: Sequence[str],
    *,
    all_sources: Optional[Sequence[str]] = None,
    module_index: Optional[ModulePathIndex] = None,
) -> List[str]:
    """
    Return source paths slang needs to elaborate ``top_modules``.

    Walks structural ``InstanceEdge`` entries (AST). Resolves child RTL via
    ``u_*`` directory naming when edge ``file_path`` metadata is wrong.
    """
    sources_list = [_resolved(s) for s in (all_sources or [])]
    idx = module_index
    if idx is None and len(sources_list) > 64:
        idx = build_module_path_index(sources_list)

    inst_lookup: Dict[InstKey, str] = {}
    if sources_list and len(sources_list) <= 64:
        inst_lookup = _build_inst_module_files(sources_list)

    reachable: Set[str] = set()
    queue: deque[str] = deque()
    for top in top_modules:
        t = (top or "").strip()
        if t and t in modules:
            queue.append(t)

    files: List[str] = []
    seen_files: Set[str] = set()

    def add_file(path: Optional[str]) -> None:
        if not path:
            return
        key = _resolved(path)
        if key not in seen_files:
            seen_files.add(key)
            files.append(key)

    for top in top_modules:
        t = (top or "").strip()
        if t and sources_list:
            add_file(
                resolve_module_source_path(
                    t, sources_list, module_index=idx
                )
            )

    while queue:
        name = queue.popleft()
        if name in reachable:
            continue
        reachable.add(name)

        rec = modules.get(name)
        if not rec:
            continue
        for edge in rec.instances:
            child_fp = _edge_source_file(
                edge,
                inst_lookup,
                modules,
                sources_list,
                module_index=idx,
            )
            add_file(child_fp)
            child = (edge.child_module or "").strip()
            if child and child_fp and child not in reachable:
                queue.append(child)
        for bind in rec.binds:
            for target in (bind.target_module, bind.child_module):
                t = (target or "").strip()
                if t and t not in reachable:
                    queue.append(t)

    if not files:
        for top in top_modules:
            t = (top or "").strip()
            if t and sources_list:
                add_file(
                    resolve_module_source_path(t, sources_list, module_index=idx)
                )
    return files