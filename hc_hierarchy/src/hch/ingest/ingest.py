"""Ingest RTL via pyslang (Tier P: preprocessor defines + -y/-v from filelist)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from hch.engine.availability import check_engine
from hch.engine.pyslang_parse import parse_config_with_diagnostics, parse_syntax_trees
from hch.ingest.filelist_config import config_from_filelist
from hch.ingest.filelist import FilelistResult, parse_filelist_simple
from hch.ingest.library_scan import scan_library_modules
from hch.ingest.merge import merge_module_records
from hch.ingest.pyslang_extract import extract_modules_from_trees, get_last_extract_stats
from hch.ingest.tree_source import pair_trees_with_sources
from hch.ingest.unresolved import collect_unresolved_modules
from hch.schema import ModuleRecord

# Last ingest diagnostics (for loader meta)
_last_parse_meta: Dict[str, str] = {}


def get_last_parse_meta() -> Dict[str, str]:
    return dict(_last_parse_meta)


def _ingest_trees_with_sources(
    trees: List,
    sources: List[str],
    preprocessor_defines: Optional[Dict[str, str]] = None,
) -> Dict[str, ModuleRecord]:
    merged: Dict[str, ModuleRecord] = {}
    pairs = pair_trees_with_sources(trees, sources)
    for tree, src in pairs:
        batch: Dict[str, ModuleRecord] = {}
        for m in extract_modules_from_trees(
            [tree], src, preprocessor_defines=preprocessor_defines
        ):
            batch[m.module_name] = m
        merge_module_records(merged, batch)
    return merged


def _require_pyslang():
    status = check_engine()
    if not status.available or status.backend != "pyslang":
        raise ImportError(status.message + (f": {status.error}" if status.error else ""))
    return status


def ingest_source_files(
    filenames: Sequence[Union[str, Path]],
    include_dirs: Optional[Sequence[str]] = None,
    defines: Optional[Dict[str, str]] = None,
    *,
    library_files: Optional[Sequence[Union[str, Path]]] = None,
    library_dirs: Optional[Sequence[Union[str, Path]]] = None,
) -> Dict[str, ModuleRecord]:
    _require_pyslang()
    paths = [Path(f).resolve() for f in filenames]
    from hch.platform_paths import path_to_slang

    inc = [path_to_slang(d) for d in (include_dirs or [])]
    trees = parse_syntax_trees(
        paths,
        include_dirs=inc,
        defines=defines,
        library_files=library_files,
        library_dirs=library_dirs,
    )
    sources = [str(p) for p in paths]
    return _ingest_trees_with_sources(trees, sources)


def ingest_filelist(
    filelist_path: Union[str, Path],
    env: Optional[Dict[str, str]] = None,
    *,
    index_cwd: Optional[Union[str, Path]] = None,
    slang_cache_path: Optional[Union[str, Path]] = None,
) -> Dict[str, ModuleRecord]:
    _require_pyslang()
    fl = parse_filelist_simple(
        str(filelist_path), env=env, index_cwd=index_cwd
    )
    if not fl.source_files:
        raise ValueError(f"No sources in filelist: {fl.errors}")
    return ingest_filelist_result(
        fl, index_cwd=index_cwd, slang_cache_path=slang_cache_path
    )


def ingest_filelist_result(
    fl: FilelistResult,
    *,
    index_cwd: Optional[Union[str, Path]] = None,
    slang_cache_path: Optional[Union[str, Path]] = None,
) -> Dict[str, ModuleRecord]:
    global _last_parse_meta
    _require_pyslang()
    cfg = config_from_filelist(
        fl,
        index_cwd=index_cwd,
        slang_cache_path=slang_cache_path,
    )
    trees, perr, pwarn, pmsgs, parse_by_file = parse_config_with_diagnostics(cfg)
    sources = list(cfg.source_files)
    merged = _ingest_trees_with_sources(trees, sources, preprocessor_defines=fl.defines)

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

    status = {
        str(p): "ok" for p in sources if Path(p).exists()
    }
    stats = get_last_extract_stats()
    cell_map = {
        name: stub.file_path
        for name, stub in stubs.items()
        if stub.file_path
    }
    defparam_n = sum(
        1
        for r in merged.values()
        for k in r.parameters
        if "." in k
    )
    primitive_n = sum(
        1 for r in merged.values() if getattr(r, "module_kind", "") == "primitive"
    ) or stats.get("primitive_count", 0)
    parse_errors_by_file: Dict[str, Dict[str, object]] = {}
    for src in sources:
        from hch.platform_paths import path_to_db

        key = path_to_db(src)
        parse_errors_by_file[key] = {
            "errors": 0,
            "warnings": 0,
            "status": status.get(str(src), "ok"),
            "messages": [],
        }
    for path, entry in parse_by_file.items():
        merged_entry = dict(entry)
        merged_entry.setdefault("messages", [])
        if path in parse_errors_by_file:
            parse_errors_by_file[path].update(merged_entry)
        else:
            parse_errors_by_file[path] = merged_entry
    for err in fl.errors:
        if "Source not found:" in err:
            path = err.split(":", 1)[-1].strip()
            parse_errors_by_file[path] = {
                "errors": 1,
                "warnings": 0,
                "status": "missing",
                "messages": [err[:200]],
            }
    if perr and not any(int(v.get("errors", 0) or 0) for v in parse_errors_by_file.values()):
        for entry in parse_errors_by_file.values():
            if entry.get("status") == "ok":
                entry["errors"] = max(int(entry.get("errors", 0)), 1)
                entry["status"] = "error"

    from hch.ingest.text_instance_fallback import supplement_modules_text_fallback

    # Parametric ``#(...)`` instances (e.g. hfa/middle_module.u_subTop_0) may be
    # dropped by pyslang even when the file parse status is ok.
    force_fallback = [
        rec.file_path
        for rec in merged.values()
        if (rec.file_path or "").endswith("middle_module.v")
    ]
    fb_stats = supplement_modules_text_fallback(
        merged,
        defines=fl.defines,
        parse_errors_by_file=parse_errors_by_file,
        force_files=force_fallback or None,
    )

    _last_parse_meta = {
        "library_y_count": str(len(fl.library_dirs)),
        "library_v_count": str(len(fl.library_files)),
        "parse_error_count": str(perr),
        "parse_warning_count": str(pwarn),
        "parse_diagnostics_json": json.dumps(pmsgs[:20]),
        "preprocess_libs_in_driver": "1",
        "source_status_json": json.dumps(status),
        "parsed_source_count": str(len(trees)),
        "defparam_count": str(defparam_n or stats.get("defparam_count", 0)),
        "primitive_count": str(primitive_n),
        "generate_loop_unroll_count": str(stats.get("generate_loop_unroll_count", 0)),
        "generate_param_bound_unresolved_count": str(
            stats.get("generate_param_bound_unresolved", 0)
        ),
        "case_generate_arm_count": str(stats.get("case_generate_arm_count", 0)),
        "generate_branch_ambiguous_count": str(
            stats.get("generate_branch_ambiguous", 0)
        ),
        "modport_instance_count": str(stats.get("modport_instance_count", 0)),
        "macro_instance_count": str(stats.get("macro_instance_count", 0)),
        "macro_definition_count": str(stats.get("macro_definition_count", 0)),
        "while_generate_placeholder_count": str(
            stats.get("while_generate_placeholder_count", 0)
        ),
        "while_generate_unroll_count": str(stats.get("while_generate_unroll_count", 0)),
        "parametric_array_expand_count": str(
            stats.get("parametric_array_expand_count", 0)
        ),
        "generate_unreachable_edge_count": str(
            stats.get("generate_unreachable_edge_count", 0)
        ),
        "generate_ambiguous_instance_count": str(
            stats.get("generate_ambiguous_instance_count", 0)
        ),
        "package_symbol_count": str(stats.get("package_symbol_count", 0)),
        "package_module_count": str(
            sum(1 for m in merged.values() if m.module_kind == "package")
        ),
        "library_cell_map_json": json.dumps(cell_map),
        "work_library": fl.work_library or "",
        "filelist_top_modules_json": json.dumps(fl.top_modules),
        "parse_errors_json": json.dumps(parse_errors_by_file),
        "text_fallback_instance_count": str(fb_stats.get("instances_added", 0)),
        "text_fallback_files_scanned": str(fb_stats.get("files_scanned", 0)),
        "text_fallback_modules_touched": str(fb_stats.get("modules_touched", 0)),
    }
    if fl.unsupported_options:
        _last_parse_meta["unsupported_filelist_opts_json"] = json.dumps(
            fl.unsupported_options[:30]
        )
    if fl.slang_options:
        _last_parse_meta["slang_options_json"] = json.dumps(fl.slang_options[:30])
    return merged