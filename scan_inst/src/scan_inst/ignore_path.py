"""Path patterns that stop hierarchy elaboration (ignorePath)."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Iterable, List, Sequence

_MODULE_NAME_RE = re.compile(
    r"\b(?:module|interface|program)\s+([A-Za-z_]\w*)\b",
    re.IGNORECASE,
)


def _split_pattern_tokens(raw: str) -> List[str]:
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _append_unique(patterns: List[str], items: Iterable[str]) -> None:
    for item in items:
        token = item.strip()
        if token and token not in patterns:
            patterns.append(token)


def load_ignore_path_file(path: str | Path) -> tuple[List[str], List[str]]:
    """
    Load ignore patterns from a hand-edited list file.

    One pattern per line. ``#`` starts a comment. Inline commas are split.
    ``module:pcie_top`` lines add module-name ignores.
    """
    p = Path(path)
    paths: List[str] = []
    modules: List[str] = []
    if not p.is_file():
        return paths, modules
    text = p.read_text(encoding="utf-8", errors="ignore")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("module:"):
            name = line.split(":", 1)[1].strip()
            _append_unique(modules, _split_pattern_tokens(name))
            continue
        _append_unique(paths, _split_pattern_tokens(line))
    return paths, modules


def load_ignore_lists(
    *,
    ignore_paths: Sequence[str] = (),
    ignore_path_files: Sequence[str | Path] = (),
    ignore_modules: Sequence[str] = (),
) -> tuple[List[str], List[str]]:
    """Merge CLI, env, files, and manual module names."""
    path_patterns: List[str] = []
    module_patterns: List[str] = []

    env = os.environ.get("SCAN_INST_IGNORE_PATH", "").strip()
    if env:
        _append_unique(path_patterns, _split_pattern_tokens(env))

    env_mod = os.environ.get("SCAN_INST_IGNORE_MODULE", "").strip()
    if env_mod:
        _append_unique(module_patterns, _split_pattern_tokens(env_mod))

    for p in ignore_paths:
        _append_unique(path_patterns, _split_pattern_tokens(p))

    for mf in ignore_path_files:
        file_paths, file_modules = load_ignore_path_file(mf)
        _append_unique(path_patterns, file_paths)
        _append_unique(module_patterns, file_modules)

    _append_unique(module_patterns, ignore_modules)
    return path_patterns, module_patterns


def resolve_ignore_path_patterns(
    ignore_paths: Sequence[str] = (),
    *,
    ignore_path_files: Sequence[str | Path] = (),
    ignore_modules: Sequence[str] = (),
) -> tuple[List[str], List[str]]:
    return load_ignore_lists(
        ignore_paths=ignore_paths,
        ignore_path_files=ignore_path_files,
        ignore_modules=ignore_modules,
    )


def _is_glob_pattern(pattern: str) -> bool:
    return any(ch in pattern for ch in ("*", "?", "["))


def _glob_matches_path(norm: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(norm, pattern):
        return True
    base = norm.rsplit("/", 1)[-1]
    if base and fnmatch.fnmatchcase(base, pattern):
        return True
    return any(fnmatch.fnmatchcase(seg, pattern) for seg in norm.split("/") if seg)


def _segment_matches(pattern: str, segment: str) -> bool:
    return pattern == segment or pattern.lower() == segment.lower()


def normalized_ignore_path(path: str | Path) -> str:
    """Canonical absolute path string for ignore-path matching."""
    try:
        return str(Path(path).resolve()).replace("\\", "/")
    except OSError:
        return str(path).replace("\\", "/")


def source_path_matches(path: str | Path, patterns: Sequence[str]) -> bool:
    if not patterns:
        return False
    norm = normalized_ignore_path(path)
    norm_lower = norm.lower()
    for pat in patterns:
        if not pat:
            continue
        if _is_glob_pattern(pat):
            if _glob_matches_path(norm, pat):
                return True
        elif pat.lower() in norm_lower:
            return True
        else:
            segments = [seg for seg in norm.split("/") if seg]
            if any(_segment_matches(pat, seg) for seg in segments):
                return True
    return False


def partition_sources(
    sources: Sequence[str],
    patterns: Sequence[str],
) -> tuple[List[str], List[str]]:
    if not patterns:
        return list(sources), []
    parse_out: List[str] = []
    ignore_out: List[str] = []
    for src in sources:
        resolved = normalized_ignore_path(src)
        if source_path_matches(resolved, patterns):
            ignore_out.append(resolved)
        else:
            parse_out.append(resolved)
    return parse_out, ignore_out


def scan_ignore_path_stubs(text: str, file_path: str) -> dict[str, "ModuleRecord"]:
    from scan_inst.models import ModuleRecord

    out: dict[str, ModuleRecord] = {}
    for m in _MODULE_NAME_RE.finditer(text):
        name = m.group(1)
        if name in out:
            continue
        out[name] = ModuleRecord(
            module_name=name,
            file_path=file_path,
            stop_reason="ignorePath",
        )
    return out