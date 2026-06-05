"""Tier E: fast closure ingest + single-pass slang parse/elaborate."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from hch.diag.elab_trace import ElabTrace

from hch.engine.elab_result import ElaborationResult
from hch.ingest.filelist import FilelistResult
from hch.ingest.ingest import (
    _ingest_trees_with_sources,
    get_last_parse_meta,
    ingest_filelist_result,
)
from hch.ingest.library_scan import scan_library_modules
from hch.ingest.merge import merge_module_records
from hch.ingest.unresolved import collect_unresolved_modules
from hch.schema import InstanceEdge, ModuleRecord

__all__ = ["ingest_for_elab", "tier_e_index_build"]

_DEFAULT_MAX_PRUNED = 256
_DEFAULT_MAX_RATIO = 0.08

_INST_RE = re.compile(
    r"(?m)^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(?:#\s*\(|\s*\()"
)


def _top_module_seed_regex(top_path: str, top_module: str) -> Dict[str, ModuleRecord]:
    try:
        text = Path(top_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    rec = ModuleRecord(module_name=top_module, file_path=str(Path(top_path).resolve()))
    seen: set[tuple[str, str]] = set()
    for child_mod, inst in _INST_RE.findall(text):
        key = (inst, child_mod)
        if key in seen:
            continue
        seen.add(key)
        rec.instances.append(
            InstanceEdge(
                parent_module=top_module,
                inst_name=inst,
                child_module=child_mod,
                file_path=rec.file_path,
            )
        )
    return {top_module: rec} if rec.instances or text else {}


def _top_module_seed(top_path: str, top_module: str) -> Dict[str, ModuleRecord]:
    """Parse top RTL with pyslang; fall back to regex when engine unavailable."""
    resolved = str(Path(top_path).resolve())
    try:
        from hch.engine.pyslang_parse import parse_syntax_trees

        trees = parse_syntax_trees(
            [resolved],
            include_dirs=[str(Path(resolved).parent)],
        )
        mods = _ingest_trees_with_sources(trees, [resolved])
        if top_module in mods and mods[top_module].instances:
            return {top_module: mods[top_module]}
    except Exception:
        pass
    return _top_module_seed_regex(top_path, top_module)


def _attach_library_stubs(merged: Dict[str, ModuleRecord], fl: FilelistResult) -> None:
    unresolved_before = set(collect_unresolved_modules(merged))
    stubs = scan_library_modules(
        fl.library_files,
        fl.library_dirs,
        libexts=fl.libexts,
    )
    for name, stub in stubs.items():
        if name in merged:
            continue
        if name not in unresolved_before:
            continue
        merge_module_records(merged, {name: stub})


def _compute_pruned_sources(
    fl: FilelistResult,
    tops: List[str],
    *,
    max_pruned: int,
    max_ratio: float,
    trace: Optional["ElabTrace"] = None,
) -> Tuple[Optional[List[str]], Dict[str, str], Dict[str, ModuleRecord]]:
    """Return (pruned paths, meta, seed modules) or (None, meta, {}) for full ingest."""
    primary = [str(p.resolve()) for p in fl.source_files]
    meta: Dict[str, str] = {
        "ingest_mode": "full",
        "ingest_source_count": str(len(primary)),
    }
    if not tops or not primary:
        if trace:
            trace.event("prune_skip", status="skip", detail={"reason": "no_tops_or_sources"})
        return None, meta, {}

    from hch.engine.elab_source_prune import (
        build_module_path_index,
        prune_sources_for_elab,
        resolve_module_source_path,
    )

    mod_index: Optional[Dict[str, List[str]]] = None
    if len(primary) > 64:
        mod_index = build_module_path_index(primary)
        meta["module_path_index_built"] = "1"
    top = tops[0]
    top_path = resolve_module_source_path(top, primary, module_index=mod_index)
    n_primary = len(primary)
    if not top_path:
        if trace:
            trace.event(
                "resolve_top",
                status="fail",
                detail={"top": top, "source_count": n_primary},
                error="top_module_source_not_found",
            )
        return None, meta, {}

    seed = _top_module_seed(top_path, top)
    pruned = prune_sources_for_elab(
        seed, tops, all_sources=primary, module_index=mod_index
    )
    n_pruned = len(pruned)
    ratio = (n_pruned / n_primary) if n_primary else 1.0
    meta["elab_closure_pruned"] = str(n_pruned)
    meta["elab_closure_ratio"] = f"{ratio:.4f}"
    if trace:
        trace.event(
            "closure_prune",
            detail={
                "top": top,
                "top_path": top_path,
                "seed_edges": len(seed[top].instances) if top in seed else 0,
                "pruned_count": n_pruned,
                "primary_count": n_primary,
                "ratio": ratio,
            },
        )

    meta["ingest_source_count"] = str(n_pruned)
    meta["ingest_pruned_from"] = str(n_primary)

    if not pruned:
        if trace:
            trace.event("closure_prune", status="fail", error="empty_closure")
        return None, meta, seed

    over_gate = n_pruned > max_pruned or (
        n_primary > 32 and ratio > max_ratio
    )
    if over_gate:
        meta["ingest_mode"] = "pruned"
        meta["elab_fast_ingest"] = "0"
        meta["tier_e_single_pass"] = "0"
        if trace:
            trace.event(
                "fast_path_gate",
                status="pruned_only",
                detail={
                    "reason": "over_threshold",
                    "max_pruned": max_pruned,
                    "max_ratio": max_ratio,
                    "n_pruned": n_pruned,
                    "ratio": ratio,
                },
            )
        return pruned, meta, seed

    meta["ingest_mode"] = "fast"
    meta["elab_fast_ingest"] = "1"
    meta["tier_e_single_pass"] = "1"
    return pruned, meta, seed


def tier_e_index_build(
    fl: FilelistResult,
    top_modules: Sequence[str],
    *,
    elab_fast: bool = True,
    instance_cap: int = 50_000,
    max_pruned: int = _DEFAULT_MAX_PRUNED,
    max_ratio: float = _DEFAULT_MAX_RATIO,
    trace: Optional["ElabTrace"] = None,
    pruned_bundle: Optional[Tuple[List[str], Dict[str, str], Dict[str, ModuleRecord]]] = None,
    slang_cache_path: Optional[str] = None,
    index_cwd: Optional[str] = None,
) -> Tuple[Dict[str, ModuleRecord], ElaborationResult, Dict[str, str]]:
    """
    Ingest + elaborate in one slang driver session when closure is small.
    """
    from hch.engine.pyslang_elab import _elaborate_parsed_driver, elaborate_filelist
    from hch.engine.pyslang_parse import configure_driver
    from hch.ingest.filelist_config import config_for_pruned_elab

    from hch.diag.elab_trace import elab_trace_from_env

    tops = [t.strip() for t in top_modules if t and str(t).strip()]
    trace = trace or elab_trace_from_env()
    if trace:
        trace.event(
            "tier_e_start",
            detail={"tops": tops, "elab_fast": elab_fast, "source_count": len(fl.source_files)},
        )
    if pruned_bundle is not None:
        pruned, meta, seed = pruned_bundle
    else:
        pruned, meta, seed = _compute_pruned_sources(
            fl, tops, max_pruned=max_pruned, max_ratio=max_ratio, trace=trace
        )

    if not elab_fast or pruned is None:
        if trace:
            trace.event("ingest_mode", status="full", detail=dict(meta))
        mods = ingest_filelist_result(
            fl, slang_cache_path=slang_cache_path, index_cwd=index_cwd
        )
        meta.update(get_last_parse_meta())
        result = elaborate_filelist(
            fl.top_path,
            top_modules=tops,
            fl=fl,
            modules=mods,
            instance_cap=instance_cap,
            prune_sources=elab_fast,
        )
        if trace:
            trace.event(
                "elab_full",
                status="ok" if result.succeeded else "fail",
                detail={
                    "succeeded": result.succeeded,
                    "partial": result.partial,
                    "instances": len(result.instances),
                    "error_count": len(result.errors),
                    "warning_count": len(result.warnings),
                    "errors_head": result.errors[:5],
                },
            )
            trace.flush_summary()
        return mods, result, meta

    if trace:
        trace.event("ingest_mode", status=meta.get("ingest_mode", "fast"), detail=dict(meta))
    cfg = config_for_pruned_elab(
        fl,
        pruned,
        index_cwd=index_cwd,
        slang_cache_path=slang_cache_path,
    )

    import pyslang

    d = pyslang.driver.Driver()
    d.addStandardArgs()
    configure_driver(d, cfg)
    d.processOptions()
    d.parseAllSources()
    mods = _ingest_trees_with_sources(
        list(d.syntaxTrees), pruned, preprocessor_defines=fl.defines
    )
    merge_module_records(mods, seed)
    _attach_library_stubs(mods, fl)
    meta.update(get_last_parse_meta())
    result = _elaborate_parsed_driver(
        d, tops, source_files=pruned, instance_cap=instance_cap
    )
    if pruned:
        n_from = len(fl.source_files)
        result.warnings.insert(
            0, f"elab_source_prune: {n_from} -> {len(pruned)} files"
        )
    if trace:
        trace.event(
            "elab_fast",
            status="ok" if result.succeeded else "fail",
            detail={
                "succeeded": result.succeeded,
                "partial": result.partial,
                "instances": len(result.instances),
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
                "errors_head": result.errors[:5],
                "warnings_head": result.warnings[:3],
            },
        )
        trace.flush_summary()
    return mods, result, meta


def ingest_for_elab(
    fl: FilelistResult,
    top_modules: Sequence[str],
    *,
    elab_fast: bool = True,
    max_pruned: int = _DEFAULT_MAX_PRUNED,
    max_ratio: float = _DEFAULT_MAX_RATIO,
) -> Tuple[Dict[str, ModuleRecord], Dict[str, str]]:
    """Ingest modules for Tier E (parse only, no elaboration)."""
    tops = [t.strip() for t in top_modules if t and str(t).strip()]
    pruned, meta, seed = _compute_pruned_sources(
        fl, tops, max_pruned=max_pruned, max_ratio=max_ratio
    )
    if not elab_fast or pruned is None:
        mods = ingest_filelist_result(fl)
        meta.update(get_last_parse_meta())
        return mods, meta

    from hch.engine.pyslang_parse import configure_driver, parse_config_with_diagnostics
    from hch.ingest.filelist_config import config_for_pruned_elab

    cfg = config_for_pruned_elab(fl, pruned)
    trees, *_ = parse_config_with_diagnostics(cfg)
    mods = _ingest_trees_with_sources(
        trees, pruned, preprocessor_defines=fl.defines
    )
    merge_module_records(mods, seed)
    _attach_library_stubs(mods, fl)
    meta.update(get_last_parse_meta())
    return mods, meta