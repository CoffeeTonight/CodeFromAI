"""Elaborated hierarchy via pyslang Compilation (Tier E)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Union

from hch.schema import ModuleRecord

from hch.engine.elab_params import parameters_from_instance_symbol
from hch.engine.elab_result import ElabInstance, ElaborationResult
from hch.engine.pyslang_parse import (
    PyslangParseConfig,
    configure_driver,
    driver_parse_diagnostics,
)
from hch.ingest.filelist import FilelistResult, parse_filelist_simple
from hch.ingest.compile_context import PyslangCompileContext
from hch.ingest.filelist_config import config_from_filelist

__all__ = [
    "ElabInstance",
    "ElaborationResult",
    "elaborate_instances",
    "elaborate_filelist",
    "elaborate_filelist_instances",
    "DEFAULT_ELAB_INSTANCE_CAP",
]

DEFAULT_ELAB_INSTANCE_CAP = 50_000


def _path_depth(path: str) -> int:
    return 0 if not path else path.count(".")


def _parent_path(path: str) -> Optional[str]:
    if "." not in path:
        return None
    return path.rsplit(".", 1)[0]


def _leaf_from_path(path: str) -> str:
    return path.split(".")[-1] if path else ""


def _collect_diagnostics(comp, diag_engine=None) -> tuple[List[str], List[str]]:
    from hch.engine.slang_diag import collect_compilation_diagnostics

    return collect_compilation_diagnostics(comp, diag_engine)


def _collect_instances(
    root,
    top_modules: Optional[Sequence[str]],
    *,
    instance_cap: int,
) -> tuple[List[ElabInstance], bool]:
    tops = set(top_modules or [])
    seen: Dict[str, ElabInstance] = {}
    cap_hit = False

    for top_inst in root.topInstances:
        top_name = str(top_inst.name)
        if tops and top_name not in tops:
            continue

        def visitor(sym) -> None:
            nonlocal cap_hit
            if cap_hit or len(seen) >= instance_cap:
                cap_hit = True
                return
            kind = str(getattr(sym, "kind", ""))
            if kind != "SymbolKind.Instance":
                return
            path = str(getattr(sym, "hierarchicalPath", "") or "")
            if not path:
                name_attr = str(getattr(sym, "name", "") or "")
                if name_attr:
                    path = name_attr
            if not path or path in seen:
                return
            mod = top_name
            body = getattr(sym, "body", None)
            if defn := getattr(body, "definition", None) if body is not None else None:
                if getattr(defn, "name", None):
                    mod = str(defn.name)
            leaf = _leaf_from_path(path)
            params = parameters_from_instance_symbol(sym)
            seen[path] = ElabInstance(
                full_path=path,
                inst_name=leaf,
                module=mod,
                depth=_path_depth(path),
                parent_path=_parent_path(path),
                param_overrides=params,
            )

        top_inst.visit(visitor)

    return list(seen.values()), cap_hit


def _elaborate_parsed_driver(
    d,
    top_modules: Optional[Sequence[str]],
    *,
    source_files: Optional[Sequence[str]] = None,
    strict: bool = False,
    instance_cap: int = DEFAULT_ELAB_INSTANCE_CAP,
    allow_partial: bool = True,
) -> ElaborationResult:
    sources: List[str] = [str(p) for p in (source_files or [])]
    if not sources:
        from hch.ingest.tree_source import source_path_from_syntax_tree

        for tree in d.syntaxTrees:
            p = source_path_from_syntax_tree(tree)
            if p and p not in sources:
                sources.append(p)
    perr, pwarn, pmsgs, _ = driver_parse_diagnostics(
        d, list(d.syntaxTrees), sources
    )
    comp = d.createCompilation()
    ok = d.runFullCompilation()
    de = getattr(d, "diagEngine", None)
    errors, warnings = _collect_diagnostics(comp, de)
    if pmsgs:
        warnings = list(pmsgs) + warnings
    if perr and not errors:
        errors.append(f"parse_errors={perr}")

    instances: List[ElabInstance] = []
    cap_hit = False
    try:
        root = comp.getRoot()
        instances, cap_hit = _collect_instances(
            root, top_modules, instance_cap=instance_cap
        )
    except Exception as exc:
        errors.append(f"instance_collect_failed: {exc}")

    if cap_hit:
        warnings.append(f"elab_instance_cap_hit: limit={instance_cap}")

    if not ok:
        if allow_partial and instances:
            return ElaborationResult(
                instances=instances,
                errors=errors or ["pyslang runFullCompilation failed"],
                warnings=warnings,
                succeeded=False,
                partial=True,
                instance_cap_hit=cap_hit,
            )
        if strict:
            raise RuntimeError("pyslang runFullCompilation failed")
        return ElaborationResult(
            instances=[],
            errors=errors or ["pyslang runFullCompilation failed"],
            warnings=warnings,
            succeeded=False,
            instance_cap_hit=cap_hit,
        )

    return ElaborationResult(
        instances=instances,
        errors=errors,
        warnings=warnings,
        succeeded=True,
        instance_cap_hit=cap_hit,
    )


def elaborate_config(
    cfg: PyslangParseConfig,
    top_modules: Optional[Sequence[str]] = None,
    *,
    strict: bool = False,
    instance_cap: int = DEFAULT_ELAB_INSTANCE_CAP,
    allow_partial: bool = True,
) -> ElaborationResult:
    import pyslang

    d = pyslang.driver.Driver()
    d.addStandardArgs()
    try:
        configure_driver(d, cfg)
    except RuntimeError as exc:
        if strict:
            raise
        return ElaborationResult(succeeded=False, errors=[str(exc)])
    d.processOptions()
    d.parseAllSources()
    return _elaborate_parsed_driver(
        d,
        top_modules,
        source_files=cfg.source_files,
        strict=strict,
        instance_cap=instance_cap,
        allow_partial=allow_partial,
    )


def elaborate_instances(
    filenames: Sequence[Union[str, Path]],
    include_dirs: Optional[Sequence[str]] = None,
    defines: Optional[dict] = None,
    top_modules: Optional[Sequence[str]] = None,
    *,
    library_files: Optional[Sequence[Union[str, Path]]] = None,
    library_dirs: Optional[Sequence[Union[str, Path]]] = None,
    libexts: Optional[Sequence[str]] = None,
    strict: bool = False,
    instance_cap: int = DEFAULT_ELAB_INSTANCE_CAP,
) -> ElaborationResult:
    paths = [str(Path(f).resolve()) for f in filenames]
    inc = [str(Path(d).resolve()) for d in (include_dirs or [])]
    defs = dict(defines or {})
    for p in paths:
        parent = str(Path(p).parent)
        if parent not in inc:
            inc.append(parent)
    cfg = PyslangParseConfig(
        source_files=paths,
        include_dirs=inc,
        defines=defs,
        library_files=[str(Path(f).resolve()) for f in (library_files or [])],
        library_dirs=[str(Path(d).resolve()) for d in (library_dirs or [])],
        libexts=list(libexts or [".v", ".sv", ".vh", ".svh"]),
    )
    return elaborate_config(
        cfg,
        top_modules=top_modules,
        strict=strict,
        instance_cap=instance_cap,
    )


def elaborate_filelist(
    filelist_path: Union[str, Path],
    top_modules: Optional[Sequence[str]] = None,
    *,
    fl: Optional[FilelistResult] = None,
    modules: Optional[Mapping[str, ModuleRecord]] = None,
    prune_sources: bool = True,
    strict: bool = False,
    instance_cap: int = DEFAULT_ELAB_INSTANCE_CAP,
    index_cwd: Optional[str] = None,
    slang_cache_path: Optional[str] = None,
) -> ElaborationResult:
    if fl is None:
        fl = parse_filelist_simple(str(filelist_path), index_cwd=index_cwd)
    tops = [t.strip() for t in (top_modules or []) if t and str(t).strip()]
    if not tops and fl.top_modules:
        tops = list(fl.top_modules)
    use_prune = bool(prune_sources and modules and tops)
    primary = [str(p.resolve()) for p in fl.source_files]
    pruned_from = len(primary)
    if use_prune:
        from hch.engine.elab_source_prune import (
            build_module_path_index,
            prune_sources_for_elab,
        )

        mod_index = build_module_path_index(primary) if len(primary) > 64 else None
        pruned = prune_sources_for_elab(
            modules,
            tops,
            all_sources=primary,
            module_index=mod_index,
        )
        ctx = PyslangCompileContext.for_pruned_closure(
            fl,
            pruned,
            index_cwd=index_cwd,
            slang_cache_path=slang_cache_path,
        )
        cfg = ctx.to_parse_config()
    else:
        cfg = config_from_filelist(
            fl,
            include_lib_sources=True,
            index_cwd=index_cwd,
            slang_cache_path=slang_cache_path,
        )
        pruned_from = len(cfg.source_files)
    result = elaborate_config(
        cfg,
        top_modules=tops or top_modules,
        strict=strict,
        instance_cap=instance_cap,
    )
    if prune_sources and modules and tops:
        result.warnings.insert(
            0,
            f"elab_source_prune: {pruned_from} -> {len(cfg.source_files)} files",
        )
    return result


def elaborate_filelist_instances(
    filelist_path: Union[str, Path],
    top_modules: Optional[Sequence[str]] = None,
) -> List[ElabInstance]:
    return elaborate_filelist(
        filelist_path, top_modules=top_modules, strict=True
    ).instances