"""Infer a primary top module when the user does not pass ``--top``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from hch.ingest.filelist import FilelistResult
from hch.ingest.hierarchy_build import elaborate_flat, find_top_modules
from hch.schema import ModuleRecord


@dataclass(frozen=True)
class TopInference:
    primary: str
    all_tops: List[str]
    method: str


def _stem_match_bonus(module_name: str, file_path: str) -> int:
    if not file_path:
        return 0
    return 1000 if Path(file_path).stem == module_name else 0


def _score_candidate(
    module_name: str,
    modules: Mapping[str, ModuleRecord],
) -> int:
    rec = modules.get(module_name)
    if rec is None:
        return 0
    flat = elaborate_flat(modules, top_module=module_name)
    return len(flat) + _stem_match_bonus(module_name, rec.file_path)


def infer_primary_top(
    modules: Mapping[str, ModuleRecord],
    *,
    candidates: Optional[Sequence[str]] = None,
) -> TopInference:
    """
    Pick one UI/default root among uninstantiated modules.

    Heuristic: filename stem match (``top_module.v`` → ``top_module``) then
    largest flattened subtree.
    """
    all_tops = sorted(candidates or find_top_modules(dict(modules)))
    if not all_tops:
        names = sorted(modules.keys())
        if not names:
            raise ValueError("no modules to infer top from")
        return TopInference(names[0], names, "only_module")
    if len(all_tops) == 1:
        return TopInference(all_tops[0], all_tops, "single_uninstantiated")

    ranked = sorted(
        ((name, _score_candidate(name, modules)) for name in all_tops),
        key=lambda item: (-item[1], item[0]),
    )
    primary = ranked[0][0]
    return TopInference(primary, all_tops, "stem_and_subtree")


def resolve_index_tops(
    modules: Mapping[str, ModuleRecord],
    fl: FilelistResult,
    filelist_path: Optional[str] = None,
) -> TopInference:
    """Resolve tops for indexing when CLI/filelist did not pin ``--top``."""
    del filelist_path  # reserved for future filelist-order hints
    if fl.top_modules:
        primary = fl.top_modules[0]
        all_tops = find_top_modules(dict(modules))
        if primary not in modules:
            return infer_primary_top(modules)
        return TopInference(primary, all_tops or [primary], "filelist_directive")
    return infer_primary_top(modules)