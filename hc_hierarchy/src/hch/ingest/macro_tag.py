"""Heuristic tagging of macro-expanded instances (Tier P)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Set


def macro_invoke_lines(source: str) -> Set[int]:
    """1-based line numbers with macro invocations (not ``define``/``include``)."""
    out: Set[int] = set()
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("`"):
            continue
        head = stripped[1:].split("(", 1)[0].strip().split()[0]
        if head in ("define", "include", "ifdef", "ifndef", "elsif", "else", "endif"):
            continue
        out.add(lineno)
    return out


def macro_inst_name_patterns(source: str) -> List[re.Pattern[str]]:
    """
    Patterns for instance leaf names likely created by body macros (e.g. ``u_``n).
    """
    patterns: List[re.Pattern[str]] = []
    if re.search(r"u_\s*``", source) or re.search(r"u_`", source):
        patterns.append(re.compile(r"^u_[A-Za-z_]\w*$"))
    if re.search(r"`\s*define\s+\w+.*\bchild\s+u", source, re.I):
        patterns.append(re.compile(r"^u_\w+$"))
    return patterns


def hierarchy_node_from_macro(item_node: Any) -> bool:
    """True when instantiation sits under slang *MacroUsage* expansion."""
    node = item_node
    depth = 0
    while node is not None and depth < 32:
        if "MacroUsage" in str(getattr(node, "kind", "")):
            return True
        node = getattr(node, "parent", None)
        depth += 1
    return False


def source_line_from_node(node: Any) -> int:
    """Best-effort 1-based line from pyslang *sourceRange*."""
    sr = getattr(node, "sourceRange", None)
    if sr is None:
        return 0
    start = getattr(sr, "start", None)
    if start is None:
        return 0
    for attr in ("line", "lineno", "lineNumber"):
        if hasattr(start, attr):
            return int(getattr(start, attr)) + 1
    text = str(start)
    m = re.search(r"\((\d+),", text)
    if m:
        return int(m.group(1)) + 1
    return 0


def instance_from_macro(
    inst_name: str,
    *,
    file_path: str,
    item_node: Any = None,
) -> bool:
    if not inst_name or not file_path:
        return False
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    macro_lines = macro_invoke_lines(source)
    if item_node is not None and hierarchy_node_from_macro(item_node):
        return True
    line = source_line_from_node(item_node) if item_node is not None else 0
    if line and macro_lines:
        if line in macro_lines:
            return True
        if re.fullmatch(r"u_[A-Za-z]\b", inst_name) and macro_lines:
            return True
        return False
    for pat in macro_inst_name_patterns(source):
        if pat.match(inst_name):
            return True
    return False