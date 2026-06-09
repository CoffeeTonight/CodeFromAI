"""
Recover hierarchy instances when pyslang parse is partial (Tier P).

Scans RTL text for ``child_mod inst_name`` patterns inside module bodies after
lightweight ``ifdef`` filtering. Only adds edges missing from the AST extract.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from hch.ingest.parse_tags import instance_edge_key
from hch.schema import InstanceEdge, ModuleRecord

_KEYWORDS = frozenset(
    {
        "module",
        "endmodule",
        "interface",
        "endinterface",
        "program",
        "endprogram",
        "package",
        "endpackage",
        "assign",
        "always",
        "always_ff",
        "always_comb",
        "initial",
        "wire",
        "wand",
        "wor",
        "reg",
        "logic",
        "input",
        "output",
        "inout",
        "parameter",
        "localparam",
        "genvar",
        "generate",
        "endgenerate",
        "begin",
        "end",
        "if",
        "else",
        "case",
        "endcase",
        "for",
        "while",
        "function",
        "endfunction",
        "task",
        "endtask",
        "typedef",
        "struct",
        "enum",
        "assert",
        "property",
        "specify",
        "endspecify",
        "primitive",
        "table",
        "endtable",
        "buf",
        "not",
        "and",
        "or",
        "nand",
        "nor",
        "xor",
        "xnor",
    }
)

_IFDEF_DIRECTIVE_RE = re.compile(
    r"`(?:ifdef|ifndef|elsif|else|endif)\b(?:\s+([A-Za-z_]\w*))?",
    re.IGNORECASE,
)
_MODULE_HEAD_RE = re.compile(
    r"\bmodule\s+([A-Za-z_]\w*)\b",
    re.IGNORECASE,
)


def _define_active(name: str, defines: Mapping[str, str]) -> bool:
    if not name:
        return False
    if name not in defines:
        return False
    val = str(defines[name]).strip().lower()
    return val not in ("", "0", "false", "1'b0", "'b0")


def _strip_comments(text: str) -> str:
    out: List[str] = []
    i = 0
    n = len(text)
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


def apply_ifdef_filter(text: str, defines: Optional[Mapping[str, str]] = None) -> str:
    """Keep only source lines active under ``defines`` (best-effort ``ifdef``)."""
    defs = dict(defines or {})
    lines_out: List[str] = []
    # Each frame: parent_active, emit_this_branch, chain_closed
    stack: List[Tuple[bool, bool, bool]] = []

    def emit_active() -> bool:
        return all(frame[1] for frame in stack)

    for raw_line in text.splitlines():
        line = raw_line
        pos = 0
        consumed_directive = False
        while True:
            m = _IFDEF_DIRECTIVE_RE.search(line, pos)
            if not m:
                break
            consumed_directive = True
            cmd = m.group(0).split()[0].lower().replace("`", "")
            macro = (m.group(1) or "").strip()
            parent = emit_active()
            if cmd == "ifdef":
                take = parent and _define_active(macro, defs)
                stack.append((parent, take, take))
            elif cmd == "ifndef":
                take = parent and not _define_active(macro, defs)
                stack.append((parent, take, take))
            elif cmd == "elsif":
                if not stack:
                    pos = m.end()
                    continue
                p_active, _, closed = stack[-1]
                if closed:
                    stack[-1] = (p_active, False, True)
                else:
                    take = p_active and _define_active(macro, defs)
                    stack[-1] = (p_active, take, take)
            elif cmd == "else":
                if not stack:
                    pos = m.end()
                    continue
                p_active, _, closed = stack[-1]
                if closed:
                    stack[-1] = (p_active, False, True)
                else:
                    stack[-1] = (p_active, p_active, True)
            elif cmd == "endif":
                if stack:
                    stack.pop()
            pos = m.end()
        if consumed_directive:
            # Drop pure directive lines; mixed RTL+directive lines are rare in fixtures.
            if _IFDEF_DIRECTIVE_RE.sub("", line).strip():
                if emit_active():
                    lines_out.append(_IFDEF_DIRECTIVE_RE.sub("", line))
            continue
        if emit_active():
            lines_out.append(line)
    return "\n".join(lines_out)


def extract_module_body(text: str, module_name: str) -> str:
    """Return the body of ``module_name`` (content between header and endmodule)."""
    clean = _strip_comments(text)
    matches = list(_MODULE_HEAD_RE.finditer(clean))
    for idx, m in enumerate(matches):
        if m.group(1) != module_name:
            continue
        start = m.end()
        end_limit = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
        chunk = clean[start:end_limit]
        depth = 1
        pos = 0
        body_end = len(chunk)
        while pos < len(chunk):
            hit = re.search(r"\b(module|endmodule)\b", chunk[pos:], re.IGNORECASE)
            if not hit:
                break
            word = hit.group(1).lower()
            if word == "module":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    body_end = pos + hit.start()
                    break
            pos += hit.end()
        return chunk[:body_end]
    return ""


def _skip_balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    if start >= len(text) or text[start] != open_ch:
        return start
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return start


def scan_hierarchy_instances(body: str) -> List[Tuple[str, str]]:
    """Find ``child_module inst_name`` pairs in a module body."""
    clean = _strip_comments(body)
    out: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    i = 0
    n = len(clean)
    while i < n:
        m = re.match(r"([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*", clean[i:])
        if not m:
            i += 1
            continue
        child_mod, inst_name = m.group(1), m.group(2)
        if child_mod.lower() in _KEYWORDS:
            i += 1
            continue
        j = i + m.end()
        while j < n and clean[j].isspace():
            j += 1
        if j < n and clean[j] == "#":
            j = _skip_balanced(clean, j + 1, "(", ")")
            while j < n and clean[j].isspace():
                j += 1
        if j >= n or clean[j] != "(":
            i += 1
            continue
        key = (inst_name, child_mod)
        if key not in seen:
            seen.add(key)
            out.append((child_mod, inst_name))
        i = j + 1
    return out


def _file_has_parse_errors(
    file_path: str,
    parse_errors_by_file: Optional[Mapping[str, object]],
) -> bool:
    if not parse_errors_by_file or not file_path:
        return False
    from hch.platform_paths import path_to_db

    key = path_to_db(file_path)
    entry = parse_errors_by_file.get(key)
    if not isinstance(entry, dict):
        return False
    return int(entry.get("errors", 0) or 0) > 0


def supplement_modules_text_fallback(
    modules: Dict[str, ModuleRecord],
    *,
    defines: Optional[Mapping[str, str]] = None,
    parse_errors_by_file: Optional[Mapping[str, object]] = None,
    force_files: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    """
    Add missing ``InstanceEdge`` rows from RTL text on parse-error files.

    Returns counters: ``files_scanned``, ``instances_added``, ``modules_touched``.
    """
    from hch.platform_paths import path_to_db

    force_set = {path_to_db(p) for p in (force_files or []) if p}

    modules_by_file: Dict[str, List[str]] = {}
    for name, rec in modules.items():
        if not rec.file_path or rec.is_blackbox:
            continue
        fp = path_to_db(rec.file_path)
        modules_by_file.setdefault(fp, []).append(name)

    files_scanned = 0
    instances_added = 0
    modules_touched = 0

    for fp, mod_names in modules_by_file.items():
        if force_set:
            if fp not in force_set:
                continue
        elif not _file_has_parse_errors(fp, parse_errors_by_file):
            continue
        path = Path(fp)
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_scanned += 1
        filtered = apply_ifdef_filter(raw, defines)
        for mod_name in mod_names:
            rec = modules.get(mod_name)
            if rec is None:
                continue
            body = extract_module_body(filtered, mod_name)
            if not body:
                continue
            text_pairs = scan_hierarchy_instances(body)
            if not text_pairs:
                continue
            seen = {instance_edge_key(e) for e in rec.instances}
            added_here = 0
            for child_mod, inst_name in text_pairs:
                edge = InstanceEdge(
                    parent_module=mod_name,
                    inst_name=inst_name,
                    child_module=child_mod,
                    file_path=rec.file_path,
                    child_kind="text_fallback",
                )
                key = instance_edge_key(edge)
                if key in seen:
                    continue
                rec.instances.append(edge)
                seen.add(key)
                added_here += 1
            if added_here:
                modules_touched += 1
                instances_added += added_here
    return {
        "files_scanned": files_scanned,
        "instances_added": instances_added,
        "modules_touched": modules_touched,
    }