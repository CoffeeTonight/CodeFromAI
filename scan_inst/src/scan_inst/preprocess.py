"""Verilog preprocessor: comments, include, define/undef, ifdef, macro expand."""

from __future__ import annotations

import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from scan_inst.ignore_path import source_path_matches
from scan_inst.progress import format_work_location

_IGNORE_PATH_STUB = "/* scan_inst: ignore-path skipped */"

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
_INCLUDE_LINE_RE = re.compile(r"^\s*`include\b", re.IGNORECASE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")

# Per-process include unit cache: (path, mtime_ns, size) -> (text, define ops).
_IncludeCacheKey = Tuple[str, int, int]
_DefineOp = Tuple[str, str, str]  # ("set"|"undef", name, value)
_INCLUDE_UNIT_CACHE: Dict[_IncludeCacheKey, Tuple[str, Tuple[_DefineOp, ...]]] = {}


def clear_include_unit_cache() -> None:
    """Drop cached include expansions (tests / long-lived workers)."""
    _INCLUDE_UNIT_CACHE.clear()


def _snapshot_include_cache() -> Dict[_IncludeCacheKey, Tuple[str, Tuple[_DefineOp, ...]]]:
    return dict(_INCLUDE_UNIT_CACHE)


def _install_include_cache_snapshot(
    snapshot: Dict[_IncludeCacheKey, Tuple[str, Tuple[_DefineOp, ...]]],
) -> None:
    """Seed worker-local include cache (required when start method is ``spawn``)."""
    _INCLUDE_UNIT_CACHE.clear()
    _INCLUDE_UNIT_CACHE.update(snapshot)


def strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT_RE.sub("", text)
    return _LINE_COMMENT_RE.sub("", text)


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


def _apply_define_ops(
    defines: MutableMapping[str, str],
    ops: Sequence[_DefineOp],
) -> None:
    for kind, name, val in ops:
        if kind == "set":
            defines[name] = val
        else:
            defines.pop(name, None)


def _collect_define_undef_ops(
    text: str,
) -> Tuple[str, Tuple[_DefineOp, ...]]:
    """Strip `` `define `` / `` `undef `` / `` `include `` lines; record define ops."""
    lines: List[str] = []
    ops: List[_DefineOp] = []
    for line in text.splitlines():
        dm = _DEFINE_LINE_RE.match(line)
        if dm:
            name = dm.group(1)
            val = (dm.group(2) or "1").strip()
            ops.append(("set", name, val))
            continue
        um = _UNDEF_LINE_RE.match(line)
        if um:
            ops.append(("undef", um.group(1), ""))
            continue
        if _INCLUDE_LINE_RE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines), tuple(ops)


def _collect_define_undef(
    text: str, defines: MutableMapping[str, str]
) -> str:
    """Apply in-file `` `define `` / `` `undef `` directives; strip those lines."""
    cleaned, ops = _collect_define_undef_ops(text)
    _apply_define_ops(defines, ops)
    return cleaned


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


def _should_skip_preprocess_path(
    path: Path | str,
    skip_path_patterns: Sequence[str],
) -> bool:
    """Skip when the resolved absolute path matches ignore-path folder patterns."""
    if not skip_path_patterns:
        return False
    try:
        resolved = path.resolve()
    except OSError:
        resolved = Path(path)
    return source_path_matches(resolved, skip_path_patterns)


def _expand_includes_once(
    text: str,
    source_file: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Set[Path],
    *,
    skip_path_patterns: Sequence[str] = (),
) -> str:
    out: List[str] = []
    last = 0
    for m in _INCLUDE_RE.finditer(text):
        out.append(text[last : m.start()])
        inc_path = _resolve_include(m.group(2).strip(), m.group(1), source_file, include_dirs)
        if inc_path is None:
            out.append(f"/* scan_inst: missing include {m.group(2)} */")
        elif _should_skip_preprocess_path(inc_path.resolve(), skip_path_patterns):
            out.append(_IGNORE_PATH_STUB)
        else:
            out.append(
                _preprocess_include_unit(
                    inc_path,
                    include_dirs,
                    defines,
                    visiting,
                    skip_path_patterns=skip_path_patterns,
                )
            )
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _include_cache_key(path: Path) -> Optional[_IncludeCacheKey]:
    try:
        st = path.stat()
        return str(path.resolve()), st.st_mtime_ns, st.st_size
    except OSError:
        return None


def _expand_include_text(
    text: str,
    path: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Set[Path],
    *,
    skip_path_patterns: Sequence[str] = (),
) -> str:
    for _ in range(32):
        expanded = _expand_includes_once(
            text,
            path,
            include_dirs,
            defines,
            visiting,
            skip_path_patterns=skip_path_patterns,
        )
        if expanded == text:
            break
        text = expanded
    return text


def _preprocess_include_unit(
    path: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Set[Path],
    *,
    skip_path_patterns: Sequence[str] = (),
) -> str:
    """Expand includes and `` `define ``/`` `undef `` only (keep `` `ifdef `` for parent)."""
    key = path.resolve()
    if _should_skip_preprocess_path(key, skip_path_patterns):
        return _IGNORE_PATH_STUB
    if key in visiting:
        return f"/* scan_inst: include cycle {path} */"
    visiting.add(key)

    cache_key = _include_cache_key(key)
    if cache_key is not None:
        hit = _INCLUDE_UNIT_CACHE.get(cache_key)
        if hit is not None:
            cleaned, ops = hit
            _apply_define_ops(defines, ops)
            return cleaned

    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    text = _expand_include_text(
        strip_comments(raw),
        path,
        include_dirs,
        defines,
        visiting,
        skip_path_patterns=skip_path_patterns,
    )
    cleaned, ops = _collect_define_undef_ops(text)
    if cache_key is not None:
        _INCLUDE_UNIT_CACHE[cache_key] = (cleaned, ops)
    _apply_define_ops(defines, ops)
    return cleaned


def preprocess_file(
    path: Path,
    include_dirs: Sequence[Path],
    defines: MutableMapping[str, str],
    visiting: Optional[Set[Path]] = None,
    *,
    skip_path_patterns: Sequence[str] = (),
) -> str:
    """Full preprocess for one translation unit."""
    if _should_skip_preprocess_path(path, skip_path_patterns):
        return _IGNORE_PATH_STUB
    visiting = visiting or set()
    text = _preprocess_include_unit(
        path,
        include_dirs,
        defines,
        visiting,
        skip_path_patterns=skip_path_patterns,
    )
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
    item: Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...], Tuple[str, ...]],
) -> Tuple[str, str]:
    src, inc_dirs, define_items, skip_patterns = item
    sp = Path(src)
    inc = [Path(p) for p in inc_dirs]
    defs: Dict[str, str] = dict(define_items)
    return str(sp.resolve()), preprocess_file(
        sp,
        inc,
        defs,
        set(),
        skip_path_patterns=skip_patterns,
    )


def _includes_in_file(
    path: Path,
    source_file: Path,
    include_dirs: Sequence[Path],
) -> List[Path]:
    """Line-oriented `` `include `` discovery (closure scan only; no full-file read)."""
    found: List[Path] = []
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            for raw_line in fh:
                line = _LINE_COMMENT_RE.sub("", raw_line)
                for m in _INCLUDE_RE.finditer(line):
                    inc_path = _resolve_include(
                        m.group(2).strip(),
                        m.group(1),
                        source_file,
                        include_dirs,
                    )
                    if inc_path is not None:
                        found.append(inc_path)
    except OSError:
        pass
    return found


def _collect_include_closure(
    sources: Sequence[str | Path],
    include_dirs: Sequence[Path],
    *,
    skip_path_patterns: Sequence[str] = (),
) -> Tuple[List[Path], int]:
    """Discover unique `` `include `` files reachable from RTL sources (light read)."""
    seen: Set[Path] = set()
    queue: List[Path] = []
    skipped = 0
    for src in sources:
        sp = Path(src)
        if _should_skip_preprocess_path(sp, skip_path_patterns):
            continue
        for inc_path in _includes_in_file(sp, sp, include_dirs):
            key = inc_path.resolve()
            if _should_skip_preprocess_path(key, skip_path_patterns):
                skipped += 1
                continue
            if key not in seen:
                seen.add(key)
                queue.append(key)
    idx = 0
    while idx < len(queue):
        path = queue[idx]
        idx += 1
        for inc_path in _includes_in_file(path, path, include_dirs):
            key = inc_path.resolve()
            if _should_skip_preprocess_path(key, skip_path_patterns):
                skipped += 1
                continue
            if key not in seen:
                seen.add(key)
                queue.append(key)
    return queue, skipped


_DEFAULT_INCLUDE_WARM_MAX = 1000


def _include_warm_policy() -> Tuple[bool, Optional[int]]:
    """Return ``(enabled, cap)``; ``cap is None`` means no limit."""
    if os.environ.get("SCAN_INST_NO_INCLUDE_WARM", "").strip().lower() in (
        "1",
        "yes",
        "true",
        "on",
    ):
        return False, None
    raw = os.environ.get("SCAN_INST_INCLUDE_WARM_MAX", "").strip()
    if not raw:
        return True, _DEFAULT_INCLUDE_WARM_MAX
    try:
        cap = int(raw)
    except ValueError:
        return True, _DEFAULT_INCLUDE_WARM_MAX
    if cap == 0:
        return True, None
    return True, max(1, cap)


def _warm_include_cache_for_sources(
    sources: Sequence[str | Path],
    include_dirs: Sequence[Path],
    base_defines: Mapping[str, str],
    *,
    skip_path_patterns: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Pre-expand shared includes once in the parent process.

    Workers receive this cache via pool initializer (``spawn``) or ``fork`` COW.
    """
    closure, skipped = _collect_include_closure(
        sources,
        include_dirs,
        skip_path_patterns=skip_path_patterns,
    )
    if skip_path_patterns and on_progress and skipped > 0:
        on_progress(
            f"preprocess: ignore-path skips {skipped} included file(s) "
            f"(resolved absolute path)"
        )
    if not closure:
        return 0

    warm_enabled, warm_cap = _include_warm_policy()
    if not warm_enabled:
        if on_progress:
            on_progress("preprocess: skip include warm (SCAN_INST_NO_INCLUDE_WARM)")
        return 0
    if warm_cap is not None and len(closure) > warm_cap:
        if on_progress:
            on_progress(
                f"preprocess: skip include warm ({len(closure)} includes > {warm_cap}; "
                f"set SCAN_INST_INCLUDE_WARM_MAX=0 for no limit)"
            )
        return 0

    if on_progress:
        on_progress(f"preprocess: warming {len(closure)} shared include(s)")
    warm_defs: Dict[str, str] = dict(base_defines)
    for path in closure:
        _preprocess_include_unit(
            path,
            include_dirs,
            warm_defs,
            set(),
            skip_path_patterns=skip_path_patterns,
        )
    return len(closure)


def _run_preprocess_tasks_serial(
    tasks: List[Tuple[str, Tuple[str, ...], Tuple[Tuple[str, str], ...]]],
    *,
    on_progress: Optional[Callable[[str], None]] = None,
    progress_every: int = 500,
    file_via_filelist: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    out: Dict[str, str] = {}
    total = len(tasks)
    for i, task in enumerate(tasks, start=1):
        key, text = _preprocess_file_task(task)
        out[key] = text
        if on_progress and (i == total or i % progress_every == 0):
            loc = format_work_location(
                task[0],
                index=i,
                total=total,
                via_map=file_via_filelist,
            )
            on_progress(f"preprocess: {i}/{total} sources — {loc}")
    return out


def preprocess_sources(
    sources: Sequence[str | Path],
    include_dirs: Sequence[str | Path],
    base_defines: Mapping[str, str],
    *,
    jobs: int = 0,
    skip_path_patterns: Sequence[str] = (),
    on_progress: Optional[Callable[[str], None]] = None,
    progress_every: int = 500,
    file_via_filelist: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Return map of source path → preprocessed text."""
    t0 = time.perf_counter()
    inc = [Path(p) for p in include_dirs]
    define_items = tuple(sorted(base_defines.items()))
    inc_dirs = tuple(str(p) for p in inc)
    src_list = [str(Path(s)) for s in sources]
    total = len(src_list)
    workers = _resolve_preprocess_jobs(jobs, total)
    if on_progress and total:
        jobs_note = "auto" if jobs == 0 else str(jobs)
        on_progress(
            f"preprocess: 0/{total} sources "
            f"({workers} workers, jobs={jobs_note})"
        )

    skip_tuple = tuple(skip_path_patterns)
    _warm_include_cache_for_sources(
        src_list,
        inc,
        base_defines,
        skip_path_patterns=skip_tuple,
        on_progress=on_progress,
    )

    tasks = [(src, inc_dirs, define_items, skip_tuple) for src in src_list]
    if workers == 1 or total <= 1:
        out = _run_preprocess_tasks_serial(
            tasks,
            on_progress=on_progress,
            progress_every=progress_every,
            file_via_filelist=file_via_filelist,
        )
    else:
        out = {}
        try:
            from scan_inst.manifest import scan_chunksize

            chunk = scan_chunksize(total, workers)
            cache_snapshot = _snapshot_include_cache()
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_install_include_cache_snapshot,
                initargs=(cache_snapshot,),
            ) as pool:
                for i, (key, text) in enumerate(
                    pool.map(_preprocess_file_task, tasks, chunksize=chunk),
                    start=1,
                ):
                    out[key] = text
                    if on_progress and (i == total or i % progress_every == 0):
                        loc = format_work_location(
                            key,
                            index=i,
                            total=total,
                            via_map=file_via_filelist,
                        )
                        on_progress(f"preprocess: {i}/{total} sources — {loc}")
        except (OSError, PermissionError, RuntimeError) as exc:
            msg = (
                f"preprocess: parallel workers failed ({exc!r}); "
                "retrying with thread pool"
            )
            if on_progress:
                on_progress(msg)
            else:
                print(f"[scan-inst] {msg}", file=sys.stderr, flush=True)
            try:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for i, (key, text) in enumerate(
                        pool.map(_preprocess_file_task, tasks),
                        start=1,
                    ):
                        out[key] = text
                        if on_progress and (i == total or i % progress_every == 0):
                            loc = format_work_location(
                                key,
                                index=i,
                                total=total,
                                via_map=file_via_filelist,
                            )
                            on_progress(f"preprocess: {i}/{total} sources — {loc}")
            except (OSError, PermissionError, RuntimeError) as exc2:
                msg2 = (
                    f"preprocess: thread pool failed ({exc2!r}); "
                    "falling back to serial"
                )
                if on_progress:
                    on_progress(msg2)
                else:
                    print(f"[scan-inst] {msg2}", file=sys.stderr, flush=True)
                out = _run_preprocess_tasks_serial(
                    tasks,
                    on_progress=on_progress,
                    progress_every=progress_every,
                    file_via_filelist=file_via_filelist,
                )

    elapsed = time.perf_counter() - t0
    if on_progress and total:
        rate = total / elapsed if elapsed > 0 else 0.0
        jobs_note = "auto" if jobs == 0 else str(jobs)
        on_progress(
            f"preprocess: done {total} sources in {elapsed:.1f}s "
            f"({rate:.1f} files/s, {workers} workers, jobs={jobs_note})"
        )
    return out