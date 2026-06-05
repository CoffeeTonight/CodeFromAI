"""Format pyslang Diagnostic objects (bindings lack .formatMessage on Diagnostic)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def diagnostic_is_error(d: Any) -> bool:
    ie = getattr(d, "isError", None)
    if callable(ie):
        try:
            return bool(ie())
        except TypeError:
            pass
    if ie is not None:
        return bool(ie)
    sev = str(getattr(d, "severity", "")).lower()
    return "error" in sev


def format_slang_diagnostic(d: Any, diag_engine: Any = None) -> str:
    if diag_engine is not None:
        fn = getattr(diag_engine, "formatMessage", None)
        if callable(fn):
            try:
                return str(fn(d))
            except Exception:
                pass
    for attr in ("formatMessage", "getMessage", "message"):
        fn = getattr(d, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    loc = getattr(d, "location", None)
    code = getattr(d, "code", "")
    args = getattr(d, "args", ()) or ()
    parts: List[str] = []
    if loc is not None:
        parts.append(str(loc))
    if code:
        parts.append(str(code))
    if args:
        parts.append(" ".join(str(a) for a in args))
    if parts:
        return ": ".join(parts)
    try:
        return str(d)
    except Exception:
        return repr(d)


def diagnostic_source_path(diag: Any, source_manager: Any = None) -> str:
    loc = getattr(diag, "location", None)
    if loc is None or source_manager is None:
        return ""
    buf = getattr(loc, "buffer", None)
    if buf is None:
        return ""
    try:
        return str(Path(source_manager.getFullPath(buf)).resolve())
    except (OSError, TypeError, AttributeError):
        return ""


def collect_tree_parse_diagnostics_by_file(
    driver: Any,
    trees: Sequence[Any],
    sources: Sequence[str],
) -> Dict[str, Dict[str, object]]:
    """Map slang syntax-tree diagnostics to originating RTL paths."""
    from collections import defaultdict

    from hch.ingest.tree_source import pair_trees_with_sources

    by_file: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {"errors": 0, "warnings": 0, "messages": [], "status": "ok"}
    )
    from hch.platform_paths import path_to_db

    for src in sources:
        by_file[path_to_db(src)]  # ensure key exists

    de = getattr(driver, "diagEngine", None)
    sm = getattr(driver, "sourceManager", None)
    for tree, src in pair_trees_with_sources(trees, sources):
        path = path_to_db(src) if src else ""
        if not path and sm is not None:
            path = diagnostic_source_path(
                getattr(tree, "root", None) or tree, sm
            )
        if not path:
            continue
        entry = by_file[path]
        td = getattr(tree, "diagnostics", None)
        if td is None:
            continue
        try:
            n = len(td)
        except TypeError:
            continue
        for i in range(n):
            d = td[i]
            msg = format_slang_diagnostic(d, de)
            msgs = entry.setdefault("messages", [])
            if isinstance(msgs, list) and len(msgs) < 8:
                msgs.append(msg[:500])
            if diagnostic_is_error(d):
                entry["errors"] = int(entry.get("errors", 0)) + 1
                entry["status"] = "error"
            else:
                entry["warnings"] = int(entry.get("warnings", 0)) + 1
                if entry.get("status") == "ok":
                    entry["status"] = "warn"
    return dict(by_file)


def collect_compilation_diagnostics(
    comp: Any,
    diag_engine: Any = None,
) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        diags = comp.getAllDiagnostics()
    except Exception:
        return errors, warnings
    for d in diags:
        msg = format_slang_diagnostic(d, diag_engine)
        if diagnostic_is_error(d):
            errors.append(msg)
        else:
            warnings.append(msg)
    return errors, warnings