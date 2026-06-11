"""Limit Tier P parse/flatten depth (flat or path-conditional)."""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from hch.ingest.library_scan import _MODULE_RE
from hch.ingest.text_instance_fallback import apply_ifdef_filter, scan_hierarchy_instances

_MODULE_BODY_RE = re.compile(
    r"\bmodule\s+([A-Za-z_]\w*)\b(.*?)\bendmodule\b",
    re.IGNORECASE | re.DOTALL,
)

_UNLIMITED = -1


def _norm_patterns(patterns: Sequence[str]) -> Tuple[str, ...]:
    return tuple(p.strip() for p in patterns if p and str(p).strip())


@dataclass(frozen=True)
class ConditionalDepthPolicy:
    """Anchor globs select branches; shallow limit elsewhere."""

    anchor_inst_patterns: Tuple[str, ...] = ()
    anchor_module_patterns: Tuple[str, ...] = ()
    anchor_legacy_patterns: Tuple[str, ...] = ()
    shallow_depth: int = 2
    global_max_depth: Optional[int] = None
    anchor_extra_depth: Optional[int] = None

    @property
    def has_anchors(self) -> bool:
        return bool(
            self.anchor_inst_patterns
            or self.anchor_module_patterns
            or self.anchor_legacy_patterns
        )

    @classmethod
    def from_sequences(
        cls,
        anchor_patterns: Sequence[str] = (),
        *,
        anchor_inst_patterns: Sequence[str] = (),
        anchor_module_patterns: Sequence[str] = (),
        anchor_legacy_patterns: Sequence[str] = (),
        shallow_depth: int = 2,
        global_max_depth: Optional[int] = None,
        anchor_extra_depth: Optional[int] = None,
    ) -> "ConditionalDepthPolicy":
        legacy = _norm_patterns(anchor_legacy_patterns) or _norm_patterns(anchor_patterns)
        inst = _norm_patterns(anchor_inst_patterns)
        module = _norm_patterns(anchor_module_patterns)
        if shallow_depth < 0:
            raise ValueError("shallow_depth must be >= 0")
        if anchor_extra_depth is not None and anchor_extra_depth < 0:
            raise ValueError("anchor_extra_depth must be >= 0")
        return cls(
            anchor_inst_patterns=inst,
            anchor_module_patterns=module,
            anchor_legacy_patterns=legacy,
            shallow_depth=shallow_depth,
            global_max_depth=global_max_depth,
            anchor_extra_depth=anchor_extra_depth,
        )


def _read_filtered(path: str, defines: Optional[Mapping[str, str]]) -> str:
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return apply_ifdef_filter(raw, defines)


def modules_defined_in_file(path: str, defines: Optional[Mapping[str, str]] = None) -> List[str]:
    text = _read_filtered(path, defines)
    return list(dict.fromkeys(m.group(1) for m in _MODULE_RE.finditer(text)))


def child_instances_in_file(
    path: str,
    parent_module: str,
    defines: Optional[Mapping[str, str]] = None,
) -> List[Tuple[str, str]]:
    """Return ``(child_module, inst_name)`` pairs from a module body."""
    text = _read_filtered(path, defines)
    for m in _MODULE_BODY_RE.finditer(text):
        if m.group(1) != parent_module:
            continue
        kids = scan_hierarchy_instances(m.group(2))
        return list(dict.fromkeys(kids))
    return []


def child_module_names_in_file(
    path: str,
    parent_module: str,
    defines: Optional[Mapping[str, str]] = None,
) -> List[str]:
    return list(dict.fromkeys(cm for cm, _ in child_instances_in_file(path, parent_module, defines)))


def build_module_primary_file_map(
    sources: Sequence[str],
    defines: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for src in sources:
        resolved = str(Path(src).resolve())
        for name in modules_defined_in_file(resolved, defines):
            out.setdefault(name, resolved)
    return out


def path_matches_anchor(
    inst_path: str,
    file_path: str,
    policy: ConditionalDepthPolicy,
    *,
    module_name: str = "",
) -> bool:
    """
    Match anchor globs per policy.

    * ``anchor_inst_patterns`` — instance leaf name only (e.g. ``u_ct``)
    * ``anchor_module_patterns`` — module type only (e.g. ``cpu_top``)
    * ``anchor_legacy_patterns`` — inst, module, or RTL file stem (``--depth-anchor``)
    """
    if not policy.has_anchors:
        return False
    leaf = inst_path.rsplit(".", 1)[-1] if inst_path else ""
    file_stem = Path(file_path).stem if file_path else ""
    checks: List[bool] = []
    if policy.anchor_inst_patterns:
        checks.append(
            any(leaf and fnmatch.fnmatch(leaf, pat) for pat in policy.anchor_inst_patterns)
        )
    if policy.anchor_module_patterns:
        checks.append(
            any(
                module_name and fnmatch.fnmatch(module_name, pat)
                for pat in policy.anchor_module_patterns
            )
        )
    if policy.anchor_legacy_patterns:
        checks.append(
            any(
                (leaf and fnmatch.fnmatch(leaf, pat))
                or (module_name and fnmatch.fnmatch(module_name, pat))
                or (file_stem and fnmatch.fnmatch(file_stem, pat))
                for pat in policy.anchor_legacy_patterns
            )
        )
    return any(checks)


def path_has_deepened_prefix(inst_path: str, prefixes: Sequence[str]) -> bool:
    for prefix in prefixes:
        p = prefix.strip()
        if not p:
            continue
        if inst_path == p or inst_path.startswith(f"{p}."):
            return True
    return False


def load_deepened_prefixes(meta: Mapping[str, str]) -> Tuple[str, ...]:
    raw = meta.get("deepened_paths_json", "").strip()
    if not raw:
        return ()
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    if isinstance(loaded, list):
        return tuple(str(p).strip() for p in loaded if str(p).strip())
    return ()


def save_deepened_prefixes(store, prefixes: Sequence[str], *, commit: bool = True) -> None:
    uniq = list(dict.fromkeys(p.strip() for p in prefixes if p and str(p).strip()))
    store.set_meta("deepened_paths_json", json.dumps(uniq), commit=commit)


def descendant_hops_for_node(
    inst_path: str,
    file_path: str,
    policy: ConditionalDepthPolicy,
    *,
    depth_from_top: int,
    deepened_prefixes: Optional[Sequence[str]] = None,
) -> int:
    """How many descendant levels to expand below *inst_path* (0 = leaf only)."""
    if deepened_prefixes and path_has_deepened_prefix(inst_path, deepened_prefixes):
        if policy.global_max_depth is None:
            return _UNLIMITED
        return max(0, policy.global_max_depth - depth_from_top)
    if path_matches_anchor(inst_path, file_path, policy):
        if policy.anchor_extra_depth is not None:
            return policy.anchor_extra_depth
        if policy.global_max_depth is None:
            return _UNLIMITED
        return max(0, policy.global_max_depth - depth_from_top)
    return policy.shallow_depth


def collect_deepen_sources(
    under_path: str,
    module_name: str,
    sources: Sequence[str],
    modules: Mapping[str, "ModuleRecord"],
    defines: Optional[Mapping[str, str]] = None,
    *,
    extra_hops: int,
) -> Set[str]:
    """RTL files to pyslang-parse when deepening below *under_path*."""
    from hch.schema import ModuleRecord

    mod_to_file = build_module_primary_file_map(sources, defines)
    parse_files: Set[str] = set()
    visited: Set[Tuple[str, str]] = set()
    queue: List[Tuple[str, str, int]] = [(module_name, under_path, extra_hops)]

    while queue:
        mod, inst_path, hops = queue.pop(0)
        key = (mod, inst_path)
        if key in visited:
            continue
        visited.add(key)
        rec = modules.get(mod)
        fp = (rec.file_path if rec else None) or mod_to_file.get(mod)
        if fp:
            parse_files.add(str(Path(fp).resolve()))
        if hops == 0 or not rec:
            continue
        for edge in rec.instances:
            child_path = f"{inst_path}.{edge.inst_name}"
            if hops == _UNLIMITED:
                child_hops = _UNLIMITED
            else:
                child_hops = hops - 1
            queue.append((edge.child_module, child_path, child_hops))

    return parse_files


def select_parse_sources_by_depth(
    top_module: str,
    sources: Sequence[str],
    max_depth: int,
    defines: Optional[Mapping[str, str]] = None,
) -> Set[str]:
    """
    Source files whose modules appear within *max_depth* instance hops from *top_module*.

    Depth 0 = top module only, 1 = top + direct children, etc.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    mod_to_file = build_module_primary_file_map(sources, defines)
    if top_module not in mod_to_file:
        return {str(Path(s).resolve()) for s in sources}

    parse_files: Set[str] = set()
    frontier: Set[str] = {top_module}
    for depth in range(max_depth + 1):
        for mod in frontier:
            fp = mod_to_file.get(mod)
            if fp:
                parse_files.add(fp)
        if depth >= max_depth:
            break
        nxt: Set[str] = set()
        for mod in frontier:
            fp = mod_to_file.get(mod)
            if not fp:
                continue
            for child in child_module_names_in_file(fp, mod, defines):
                nxt.add(child)
        frontier = nxt
    return parse_files


def classify_parse_sources_conditional(
    top_module: str,
    sources: Sequence[str],
    policy: ConditionalDepthPolicy,
    defines: Optional[Mapping[str, str]] = None,
) -> Tuple[Set[str], Set[str]]:
    """
    BFS from *top_module*; split sources into full (pyslang) vs skim (text-only).

    *full* — anchor-matched instance paths and all descendants under those branches.
    *skim* — shallow-zone files not reached from any anchor branch.
    """
    mod_to_file = build_module_primary_file_map(sources, defines)
    if top_module not in mod_to_file:
        all_paths = {str(Path(s).resolve()) for s in sources}
        return all_paths, set()

    full_files: Set[str] = set()
    skim_files: Set[str] = set()
    visited: Set[Tuple[str, str]] = set()
    queue: List[Tuple[str, str, int, bool]] = [
        (top_module, top_module, _UNLIMITED, False)
    ]

    while queue:
        mod, inst_path, hops, full_branch = queue.pop(0)
        key = (mod, inst_path)
        if key in visited:
            continue
        visited.add(key)
        fp = mod_to_file.get(mod)
        on_anchor = path_matches_anchor(
            inst_path,
            fp or "",
            policy,
            module_name=mod,
        )
        effective_full = full_branch or on_anchor
        if fp:
            if effective_full:
                full_files.add(fp)
                skim_files.discard(fp)
            elif fp not in full_files:
                skim_files.add(fp)
        if hops == 0 or not fp:
            continue
        for child_mod, inst_name in child_instances_in_file(fp, mod, defines):
            child_path = f"{inst_path}.{inst_name}" if inst_path else inst_name
            child_file = mod_to_file.get(child_mod, "")
            child_on_anchor = path_matches_anchor(
                child_path,
                child_file,
                policy,
                module_name=child_mod,
            )
            if child_on_anchor:
                if policy.anchor_extra_depth is not None:
                    child_hops = policy.anchor_extra_depth
                    child_full = True
                elif policy.global_max_depth is None:
                    child_hops = _UNLIMITED
                    child_full = True
                else:
                    child_hops = max(
                        0, policy.global_max_depth - child_path.count(".")
                    )
                    child_full = True
            elif full_branch and hops == _UNLIMITED:
                child_hops = _UNLIMITED
                child_full = True
            elif full_branch and hops > 0:
                child_hops = hops - 1
                child_full = True
            elif hops == _UNLIMITED:
                child_hops = policy.shallow_depth
                child_full = False
            else:
                child_hops = hops - 1
                child_full = full_branch
            queue.append((child_mod, child_path, child_hops, child_full))

    return full_files, skim_files


def select_parse_sources_conditional(
    top_module: str,
    sources: Sequence[str],
    policy: ConditionalDepthPolicy,
    defines: Optional[Mapping[str, str]] = None,
) -> Set[str]:
    """
    BFS from *top_module* with anchor-aware depth.

    Paths matching anchor rules use ``anchor_extra_depth`` when set,
    else ``global_max_depth`` (or unlimited). Other paths use ``shallow_depth``.
    """
    full_files, skim_files = classify_parse_sources_conditional(
        top_module, sources, policy, defines
    )
    return full_files | skim_files


def should_expand_flat_children(
    inst_path: str,
    file_path: str,
    depth: int,
    *,
    max_depth: Optional[int] = None,
    policy: Optional[ConditionalDepthPolicy] = None,
    descendant_hops: Optional[int] = None,
) -> bool:
    """Whether flatten walk should recurse into instance children."""
    if policy is not None:
        hops = (
            descendant_hops
            if descendant_hops is not None
            else descendant_hops_for_node(inst_path, file_path, policy, depth_from_top=depth)
        )
        if hops == 0:
            return False
        if max_depth is not None and depth >= max_depth and hops == _UNLIMITED:
            return False
        if max_depth is not None and depth >= max_depth and hops != _UNLIMITED:
            return False
        return True
    if max_depth is not None and depth >= max_depth:
        return False
    return True