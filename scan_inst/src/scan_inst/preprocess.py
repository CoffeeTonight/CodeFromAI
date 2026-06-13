"""Verilog preprocessor: comments, include, define/undef, ifdef, macro expand."""

from __future__ import annotations

import re
from pathlib import Path
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

_IFDEF_RE = re.compile(
    r"`(?:ifdef|ifndef)\s+([A-Za-z_]\w*)"
    r"|`elsif\s+([A-Za-z_]\w*)"
    r"|`(?:else|endif)\b",
    re.IGNORECASE,
)
_DEFINE_LINE_RE = re.compile(
    r"^\s*`define\s+([A-Za-z_]\w*)(?:\s+(.*))?$",
    re.IGNORECASE | re.MULTILINE,
)
_UNDEF_LINE_RE = re.compile(
    r"^\s*`undef\s+([A-Za-z_]\w*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_INCLUDE_RE = re.compile(
    r"`include\s+([<\"])([^\">]+)[\">]",
    re.IGNORECASE,
)
_MACRO_USE_RE = re.compile(r"`([A-Za-z_]\w*)")
_BIND_LINE_RE = re.compile(r"^\s*bind\b", re.IGNORECASE | re.MULTILINE)


def strip_comments(text: str) -> str:
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if text.startswith("/*", i):
            i += 2
            while i < n - 1 and text[i : i + 2] != "*/":
                i += 1
            i = min(n, i + 2)
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _define_active(name: str, defines: Mapping[str, str]) -> bool:
    if not name or name not in defines:
        return False
    val = str(defines[name]).strip().lower()
    return val not in ("", "0", "false", "1'b0", "'b0", "1'h0", "'h0")


def _apply_ifdef_directive(
    cmd: str,
    macro: str,
    stack: List[Tuple[bool, bool, bool]],
    defs: Mapping[str, str],
) -> None:
    parent = all(frame[1] for frame in stack)
    if cmd == "ifdef":
        take = parent and _define_active(macro, defs)
        stack.append((parent, take, take))
    elif cmd == "ifndef":
        take = parent and not _define_active(macro, defs)
        stack.append((parent, take, take))
    elif cmd == "elsif":
        if stack:
            p_active, _, closed = stack[-1]
            if closed:
                stack[-1] = (p_active, False, True)
            else:
                take = p_active and _define_active(macro, defs)
                stack[-1] = (p_active, take, take)
    elif cmd == "else":
        if stack:
            p_active, _, closed = stack[-1]
            if closed:
                stack[-1] = (p_active, False, True)
            else:
                stack[-1] = (p_active, p_active, True)
    elif cmd == "endif" and stack:
        stack.pop()


def _emit_ifdef_line_segments(
    line: str,
    stack: List[Tuple[bool, bool, bool]],
    defs: Mapping[str, str],
) -> List[str]:
    """Split one source line on inline `` `ifdef `` directives; emit active segments."""
    segments: List[str] = []
    pos = 0
    while True:
        m = _IFDEF_RE.search(line, pos)
        if not m:
            rest = line[pos:].strip()
            if rest and all(frame[1] for frame in stack):
                segments.append(rest)
            break
        before = line[pos : m.start()].strip()
        if before and all(frame[1] for frame in stack):
            segments.append(before)
        raw = m.group(0).lower()
        if raw.startswith("`ifdef"):
            cmd, macro = "ifdef", (m.group(1) or "").strip()
        elif raw.startswith("`ifndef"):
            cmd, macro = "ifndef", (m.group(1) or "").strip()
        elif raw.startswith("`elsif"):
            cmd, macro = "elsif", (m.group(2) or "").strip()
        elif raw.startswith("`else"):
            cmd, macro = "else", ""
        else:
            cmd, macro = "endif", ""
        _apply_ifdef_directive(cmd, macro, stack, defs)
        pos = m.end()
    return segments


def apply_ifdef_filter(text: str, defines: Mapping[str, str]) -> str:
    defs = dict(defines)
    lines_out: List[str] = []
    stack: List[Tuple[bool, bool, bool]] = []

    for raw_line in text.splitlines():
        segments = _emit_ifdef_line_segments(raw_line, stack, defs)
        if segments:
            lines_out.append(" ".join(segments))
    return "\n".join(lines_out)


def _resolve_include(
    name: str,
    bracket: str,
    source_file: Path,
    include_dirs: Sequence[Path],
) -> Optional[Path]:
    if bracket == "<":
        for d in include_dirs:
            p = (d / name).resolve()
            if p.is_file():
                return p
        return None
    p = (source_file.parent / name).resolve()
    if p.is_file():
        return p
    for d in include_dirs:
        p = (d / name).resolve()
        if p.is_file():
            return p
    return None


def _collect_define_undef(
    text: str, defines: MutableMapping[str, str]
) -> str:
    """Apply in-file `` `define `` / `` `undef `` directives; strip those lines."""
    lines: List[str] = []
    for line in text.splitlines():
        dm = re.match(r"^\s*`define\s+([A-Za-z_]\w*)(?:\s+(.*))?$", line, re.I)
        if dm:
            name = dm.group(1)
            val = (dm.group(2) or "1").strip()
            defines[name] = val
            continue
        um = re.match(r"^\s*`undef\s+([A-Za-z_]\w*)\s*$", line, re.I)
        if um:
            defines.pop(um.group(1), None)
            continue
        if re.match(r"^\s*`include\b", line, re.I):
            continue
        lines.append(line)
    return "\n".join(lines)


def _expand_macros(text: str, defines: Mapping[str, str]) -> str:
    """Replace `` `MACRO `` tokens (non function-like)."""
    skip = {
        "ifdef", "ifndef", "elsif", "else", "endif",
        "define", "undef", "include",
    }

    def repl(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in skip:
            return m.group(0)
        if name not in defines:
            return m.group(0)
        body = str(defines[name])
        if "(" in body:
            return m.group(0)
        return body

    return _MACRO_USE_RE.sub(repl, text)


def _expand_includes_once(
    text: str,
    source_file: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Set[Path],
) -> str:
    out: List[str] = []
    last = 0
    for m in _INCLUDE_RE.finditer(text):
        out.append(text[last : m.start()])
        inc_path = _resolve_include(m.group(2).strip(), m.group(1), source_file, include_dirs)
        if inc_path is None:
            out.append(f"/* scan_inst: missing include {m.group(2)} */")
        else:
            out.append(
                _preprocess_include_unit(
                    inc_path,
                    include_dirs,
                    defines,
                    visiting,
                )
            )
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _preprocess_include_unit(
    path: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Set[Path],
) -> str:
    """Expand includes and `` `define ``/`` `undef `` only (keep `` `ifdef `` for parent)."""
    key = path.resolve()
    if key in visiting:
        return f"/* scan_inst: include cycle {path} */"
    visiting.add(key)
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    text = strip_comments(raw)
    for _ in range(32):
        expanded = _expand_includes_once(text, path, include_dirs, defines, visiting)
        if expanded == text:
            break
        text = expanded
    return _collect_define_undef(text, defines)


def preprocess_file(
    path: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Optional[Set[Path]] = None,
) -> str:
    """Full preprocess for one translation unit."""
    visiting = visiting or set()
    text = _preprocess_include_unit(path, include_dirs, defines, visiting)
    text = _expand_macros(text, defines)
    text = apply_ifdef_filter(text, defines)
    text = _BIND_LINE_RE.sub("", text)
    return text


def _resolve_preprocess_jobs(jobs: int, num_tasks: int) -> int:
    if jobs < 0:
        return 1
    if jobs == 0:
        cpu = os.cpu_count() or 1
        return max(1, min(cpu, num_tasks))
    return max(1, min(jobs, num_tasks))


def _preprocess_file_task(
    item: Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...]],
) -> Tuple[str, str]:
    src, inc_dirs, define_items = item
    sp = Path(src)
    inc = [Path(p) for p in inc_dirs]
    defs: Dict[str, str] = dict(define_items)
    return str(sp.resolve()), preprocess_file(sp, inc, defs, set())


def preprocess_sources(
    sources: Sequence[str | Path],
    include_dirs: Sequence[str | Path],
    base_defines: Mapping[str, str],
    *,
    jobs: int = 0,
    on_progress: Optional[Callable[[str], None]] = None,
    progress_every: int = 500,
) -> Dict[str, str]:
    """Return map of source path → preprocessed text."""
    inc = [Path(p) for p in include_dirs]
    define_items = tuple(sorted(base_defines.items()))
    inc_dirs = tuple(str(p) for p in inc)
    src_list = [str(Path(s)) for s in sources]
    total = len(src_list)
    if on_progress and total:
        workers = _resolve_preprocess_jobs(jobs, total)
        on_progress(f"preprocess: 0/{total} sources ({workers} workers)")

    tasks = [(src, inc_dirs, define_items) for src in src_list]
    out: Dict[str, str] = {}
    workers = _resolve_preprocess_jobs(jobs, total)
    if workers == 1 or total <= 1:
        for i, task in enumerate(tasks, start=1):
            key, text = _preprocess_file_task(task)
            out[key] = text
            if on_progress and (i == total or i % progress_every == 0):
                on_progress(f"preprocess: {i}/{total} sources")
        return out

    try:
        from scan_inst.manifest import scan_chunksize

        chunk = scan_chunksize(total, workers)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, (key, text) in enumerate(
                pool.map(_preprocess_file_task, tasks, chunksize=chunk),
                start=1,
            ):
                out[key] = text
                if on_progress and (i == total or i % progress_every == 0):
                    on_progress(f"preprocess: {i}/{total} sources")
    except (OSError, PermissionError, RuntimeError):
        for i, task in enumerate(tasks, start=1):
            key, text = _preprocess_file_task(task)
            out[key] = text
            if on_progress and (i == total or i % progress_every == 0):
                on_progress(f"preprocess: {i}/{total} sources")
    return out